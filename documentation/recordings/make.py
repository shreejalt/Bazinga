"""Record every clip in Bazinga's documentation and turn it into small web videos.

Run it from the repository root with the template's own Python (the one that has requirements.txt installed):

    .venv/bin/python documentation/recordings/make.py              # every clip
    .venv/bin/python documentation/recordings/make.py figure-slider build   # just these
    .venv/bin/python documentation/recordings/make.py --convert-only        # re-encode the last raw recordings
    .venv/bin/python documentation/recordings/make.py banner                # the README/docs banner GIFs
    .venv/bin/python documentation/recordings/make.py --list

What it does, in order:

1. Copies the template (every file git tracks, minus documentation/) into .cache/recordings/site and makes it a fresh
   git repository, so clips start from the example site exactly as a new user gets it and never touch your files.
2. Terminal clips: runs each tapes/<name>.tape with VHS (https://github.com/charmbracelet/vhs).
3. Browser clips: starts `python -m bazinga serve` on the work copy (port 8020, the Editor on 8021) and runs each
   clips/<name>.mjs with Playwright (lib/run.mjs), which records the page with a visible cursor.
4. Converts every raw recording with ffmpeg: trimmed and sped up as the clip asks, to MP4 (H.264, +faststart, no
   audio) and WebM (VP9), plus a poster frame (JPEG). Clips with `gif` set also get a 640-px GIF for the README,
   made with gifski when it is installed, else with ffmpeg's palettegen/paletteuse.

Output: documentation/assets/clips/<name>.{mp4,webm,jpg} and documentation/assets/gifs/<name>.gif.
Needs: node + `npm install` in documentation/recordings, Google Chrome, ffmpeg, vhs (and ttyd); gifski is optional.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
DOCS = HERE.parent
WORK = REPO / ".cache" / "recordings"      # outside documentation/, so MkDocs never sees it
SITE = WORK / "site"
RAW = WORK / "raw"
CLIPS_OUT = DOCS / "assets" / "clips"
GIFS_OUT = DOCS / "assets" / "gifs"
BRAND_OUT = DOCS / "assets" / "brand"
PORT, EDITOR_PORT = 8020, 8021
FPS = 25
COLOUR = ["-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709"]


def run(cmd, **kw):
    shown = [str(c).replace(str(REPO) + "/", "") for c in cmd]
    print("  $ " + " ".join(shown[:14]) + (" …" if len(shown) > 14 else ""), flush=True)
    return subprocess.run([str(c) for c in cmd], check=True, **kw)


def tool(name: str, required: bool = True) -> str | None:
    found = shutil.which(name)
    if not found and required:
        sys.exit(f"{name} is not installed. See documentation/contributing/recording-clips.md.")
    return found


# ------------------------------------------------------------------------------------------------- the work copy
def prepare_site(site: Path = SITE, overlay: str = "") -> None:
    """A fresh copy of the template as a new user has it, as its own git repository.

    With `overlay` (a folder name under recordings/sites/), the paths listed in its REMOVE file are deleted first and
    its files are then copied over the example site: that is how the portfolio clip gets a portfolio-only site."""
    shutil.rmtree(site, ignore_errors=True)
    site.mkdir(parents=True)
    RAW.mkdir(parents=True, exist_ok=True)
    files = subprocess.run(["git", "ls-files", "-z"], cwd=REPO, check=True, capture_output=True).stdout
    for rel in files.decode().split("\0"):
        if not rel or rel.startswith("documentation/") or rel == "mkdocs.yml":
            continue
        src = REPO / rel
        if src.is_file():
            dst = site / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    if overlay:
        extra = HERE / "sites" / overlay
        remove = extra / "REMOVE"
        for line in (remove.read_text(encoding="utf-8").splitlines() if remove.exists() else []):
            line = line.strip()
            if line and not line.startswith("#"):
                target = site / line
                shutil.rmtree(target) if target.is_dir() else target.unlink(missing_ok=True)
        for src in extra.rglob("*"):
            if src.is_file() and src.name != "REMOVE":
                dst = site / src.relative_to(extra)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
    env = dict(os.environ, GIT_AUTHOR_NAME="Your Name", GIT_AUTHOR_EMAIL="you@example.com",
               GIT_COMMITTER_NAME="Your Name", GIT_COMMITTER_EMAIL="you@example.com")
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=site, check=True)
    subprocess.run(["git", "add", "-A"], cwd=site, check=True)
    subprocess.run(["git", "commit", "-qm", "The example site"], cwd=site, check=True, env=env)
    print(f"Work copy ready: {site.relative_to(REPO) if site.is_relative_to(REPO) else site}")


def tool_env() -> dict:
    """The template's Python first on PATH, so `python -m bazinga` works inside tapes and the server."""
    bindir = str(Path(sys.executable).parent)
    env = dict(os.environ, PATH=bindir + os.pathsep + os.environ.get("PATH", ""))
    env["BAZINGA_PYTHON"] = sys.executable
    env["BAZINGA_BIN"] = bindir                # tapes put it first on PATH in their hidden setup
    env["BASH_SILENCE_DEPRECATION_WARNING"] = "1"
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"    # its notice would print a path of this computer
    env.pop("LLM_API_KEY", None)          # clips never use a model or a key
    return env


# --------------------------------------------------------------------------------------------------- terminal
def tape_meta(path: Path) -> dict:
    """`# caption: …`, `# speed: 1.5`, `# trim: 0.5 1`, `# gif: true` comment lines at the top of a tape."""
    meta = {"name": path.stem, "speed": 1.0, "trim": [0, 0], "gif": False, "startAt": 0}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"#\s*(caption|speed|trim|gif|poster|gif_width|gif_start|gif_seconds)\s*:\s*(.+)$", line.strip())
        if not m:
            continue
        key, value = m.groups()
        if key in ("speed", "poster", "gif_start", "gif_seconds"):
            meta[key] = float(value)
        elif key == "gif_width":
            meta[key] = int(value)
        elif key == "trim":
            meta["trim"] = [float(v) for v in value.split()]
        elif key == "gif":
            meta["gif"] = value.strip().lower() in ("true", "yes", "1")
        else:
            meta[key] = value.strip()
    return meta


# Some commands print the path of the Python running them (Publish shows "$ <python> -m bazinga build"). So that a
# terminal clip never shows a folder of this computer, tapes use a Python environment at a neutral path.
TAPE_DIR = Path("/tmp/bazinga-clips")            # tapes run in TAPE_DIR/site; some commands print full paths
TAPE_VENV = TAPE_DIR / ".venv"


def tape_python() -> Path:
    """A virtual environment at /tmp/bazinga-clips/.venv with requirements.txt installed (made once)."""
    if not (TAPE_VENV / "bin" / "python").exists():
        print(f"Making {TAPE_VENV} for the terminal clips (once)")
        run([sys.executable, "-m", "venv", TAPE_VENV])
        run([TAPE_VENV / "bin" / "python", "-m", "pip", "install", "-q", "--disable-pip-version-check",
             "-r", REPO / "requirements.txt"])
    return TAPE_VENV / "bin"


def record_tape(path: Path) -> None:
    vhs = tool("vhs")
    tool("ttyd")
    env = tool_env()
    env["BAZINGA_BIN"] = str(tape_python())
    prepare_site(TAPE_DIR / "site")
    made = TAPE_DIR / "raw" / f"{path.stem}.mp4"
    made.unlink(missing_ok=True)
    # VHS writes the file named by the tape's Output line (raw/<name>.mp4), relative to the folder it runs in.
    run([vhs, path], cwd=TAPE_DIR, env=env)
    if not made.exists():
        sys.exit(f"{path.name} did not write raw/{path.stem}.mp4 (check its Output line)")
    shutil.move(made, RAW / f"{path.stem}.mp4")
    (RAW / f"{path.stem}.json").write_text(json.dumps(tape_meta(path), indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------------------------------- browser
class Server:
    """`python -m bazinga serve` on a work copy, with the Editor, for as long as its browser clips run."""

    def __init__(self, site: Path = SITE, port: int = PORT):
        self.proc, self.site, self.port = None, site, port

    def __enter__(self):
        log = open(WORK / f"serve-{self.port}.log", "w")
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "bazinga", "serve", "--port", str(self.port), "--studio-port", str(self.port + 1)],
            cwd=self.site, env=tool_env(), stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        for _ in range(120):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{self.port}/", timeout=1).read()
                print(f"{self.site.name} at http://127.0.0.1:{self.port}/ (Editor on {self.port + 1})")
                return self
            except OSError:
                if self.proc.poll() is not None:
                    sys.exit(f"the server stopped; see {WORK / f'serve-{self.port}.log'}")
                time.sleep(0.5)
        sys.exit("the server did not start within 60 s")

    def __exit__(self, *exc):
        if self.proc and self.proc.poll() is None:
            os.killpg(self.proc.pid, signal.SIGINT)
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                os.killpg(self.proc.pid, signal.SIGKILL)


def clip_site(path: Path) -> str:
    """The `site: "<name>"` a clip asks for in its meta (a folder under recordings/sites/), or "" for the example."""
    m = re.search(r'\bsite:\s*"([a-z0-9-]+)"', path.read_text(encoding="utf-8"))
    return m.group(1) if m else ""


def record_clip(path: Path, port: int = PORT) -> bool:
    node = tool("node")
    if not (HERE / "node_modules" / "playwright").exists():
        sys.exit("Playwright is missing: run `npm install` in documentation/recordings first.")
    env = tool_env()
    env["BASE_URL"] = f"http://127.0.0.1:{port}"
    try:
        run([node, HERE / "lib" / "run.mjs", path, RAW], cwd=HERE, env=env)
        return True
    except subprocess.CalledProcessError:
        return False


# ---------------------------------------------------------------------------------------------------- convert
def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         check=True, capture_output=True, text=True).stdout
    return float(out.strip() or 0)


def frame_list(name: str, meta: dict, frames_dir: Path) -> Path:
    """An ffmpeg concat list: each filmed frame shown until the next one, with the cut stretches taken out."""
    frames = sorted(json.loads((frames_dir / "frames.json").read_text(encoding="utf-8")), key=lambda f: f[1])
    start = float(meta.get("startAt") or 0) + float(meta["trim"][0])
    end = float(meta["endAt"]) - float(meta["trim"][1] if len(meta["trim"]) > 1 else 0)
    keep, a = [], start
    for s0, s1 in sorted(meta.get("skips") or []):
        if s1 <= a or s0 >= end:
            continue
        if s0 > a:
            keep.append((a, s0))
        a = max(a, s1)
    if a < end:
        keep.append((a, end))
    shown, offset = [], 0.0          # (file, time in the finished clip)
    for a, b in keep:
        before = [f for f in frames if f[1] <= a]
        first = before[-1] if before else frames[0]
        shown.append((first[0], offset))
        shown += [(f, offset + t - a) for f, t in frames if a < t < b]
        offset += b - a
    lines = ["ffconcat version 1.0"]
    for i, (f, t) in enumerate(shown):
        nxt = shown[i + 1][1] if i + 1 < len(shown) else offset
        lines += [f"file '{frames_dir / f}'", f"duration {max(nxt - t, 0.001):.4f}"]
    lines.append(f"file '{frames_dir / shown[-1][0]}'")
    out = frames_dir / "list.ffconcat"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def convert(name: str) -> dict:
    ffmpeg = tool("ffmpeg")
    meta = json.loads((RAW / f"{name}.json").read_text(encoding="utf-8"))
    frames_dir = RAW / f"{name}-frames"
    terminal = not frames_dir.exists()
    speed = float(meta.get("speed") or 1)
    CLIPS_OUT.mkdir(parents=True, exist_ok=True)
    if terminal:
        # a VHS recording: trim, speed up, steady frame rate
        src = RAW / f"{name}.mp4"
        start = float(meta["trim"][0])
        end = duration(src) - float(meta["trim"][1] if len(meta["trim"]) > 1 else 0)
        inputs = ["-i", src]
        vf = (f"trim=start={start:.3f}:end={end:.3f},setpts=(PTS-STARTPTS)/{speed},fps={FPS},"
              "scale='min(1280,iw)':-2:flags=lanczos,format=yuv420p")
    else:
        # a browser clip: frames filmed at 2x, each with its time; keep start..end minus the cut stretches
        inputs = ["-f", "concat", "-safe", "0", "-i", frame_list(name, meta, frames_dir)]
        # Chrome's JPEGs are full-range BT.601; videos for the web are limited-range BT.709, so convert both.
        vf = (f"setpts=PTS/{speed},fps={FPS},scale=1280:-2:flags=lanczos:in_range=pc:out_range=tv:"
              "in_color_matrix=bt601:out_color_matrix=bt709,format=yuv420p")
    base = CLIPS_OUT / name
    crf = str(meta.get("crf") or 23)        # lower is sharper and bigger; a clip that scrolls a lot may want 27
    run([ffmpeg, "-y", "-loglevel", "error", *inputs, "-vf", vf, "-an", "-c:v", "libx264", "-preset", "slow",
         "-crf", crf, "-pix_fmt", "yuv420p", *COLOUR, "-movflags", "+faststart", f"{base}.mp4"])
    run([ffmpeg, "-y", "-loglevel", "error", *inputs, "-vf", vf, "-an", "-c:v", "libvpx-vp9", "-crf", "38",
         "-b:v", "0", "-row-mt", "1", "-deadline", "good", "-cpu-used", "2", *COLOUR, f"{base}.webm"])
    length = duration(Path(f"{base}.mp4"))
    at = meta.get("poster")
    at = length - 0.3 if at is None else min(float(at), length - 0.1)
    run([ffmpeg, "-y", "-loglevel", "error", "-ss", f"{max(0, at):.2f}", "-i", f"{base}.mp4", "-frames:v", "1",
         "-q:v", "4", f"{base}.jpg"])
    sizes = {ext: Path(f"{base}.{ext}").stat().st_size for ext in ("mp4", "webm", "jpg")}
    # What the docs' clip frame shows in its top bar: the page address, or "Terminal".
    w, hgt = (int(v) for v in subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0",
         f"{base}.mp4"], check=True, capture_output=True, text=True).stdout.strip().split(","))
    Path(f"{base}.json").write_text(json.dumps({
        "kind": "terminal" if terminal else "browser",
        "bar": meta.get("bar") or ("Terminal" if terminal else "127.0.0.1:8000" + (meta.get("path") or "/")),
        "caption": meta.get("caption", ""), "seconds": round(length, 1), "width": w, "height": hgt,
    }, indent=2) + "\n", encoding="utf-8")
    if meta.get("gif"):
        sizes["gif"] = make_gif(Path(f"{base}.mp4"), GIFS_OUT / f"{name}.gif", int(meta.get("gif_width") or 640),
                                start=float(meta.get("gif_start") or 0), seconds=float(meta.get("gif_seconds") or 8))
    return {"name": name, "seconds": round(length, 1), **sizes}


def make_gif(src: Path, out: Path, width: int, fps: int = 10, start: float = 0, seconds: float = 8) -> int:
    """A short GIF for the README (GitHub does not autoplay video there): `seconds` long from `start`."""
    ffmpeg = tool("ffmpeg")
    out.parent.mkdir(parents=True, exist_ok=True)
    gifski = tool("gifski", required=False)
    if gifski:
        frames = WORK / "gif-frames"
        shutil.rmtree(frames, ignore_errors=True)
        frames.mkdir(parents=True)
        run([ffmpeg, "-loglevel", "error", "-ss", f"{start}", "-t", f"{seconds}", "-i", src,
             "-vf", f"fps={fps},scale={width}:-2:flags=lanczos",
             frames / "f%04d.png"])
        run([gifski, "--quiet", "--fps", str(fps), "--width", str(width), "--quality", "60", "-o", out,
             *sorted(frames.glob("f*.png"))])
        shutil.rmtree(frames, ignore_errors=True)
    else:
        run([ffmpeg, "-y", "-loglevel", "error", "-ss", f"{start}", "-t", f"{seconds}", "-i", src, "-vf",
             f"fps={fps},scale={width}:-2:flags=lanczos,split[a][b];[a]palettegen=max_colors=96:stats_mode=diff[p];"
             "[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle", out])
    return out.stat().st_size


# ----------------------------------------------------------------------------------------------------- banner
def make_banner() -> None:
    """The banner GIFs at the top of the README and the docs home, from documentation/assets/brand/source/
    (banner.html draws a frame for any time t; frames.mjs saves every frame; see that folder's README.md)."""
    source = DOCS / "assets" / "brand" / "source"
    if not (source / "frames.mjs").exists():
        sys.exit("documentation/assets/brand/source/frames.mjs is missing")
    ffmpeg, node = tool("ffmpeg"), tool("node")
    gifsicle = tool("gifsicle", required=False)
    for theme in ("light", "dark"):
        frames = WORK / f"banner-frames-{theme}"
        shutil.rmtree(frames, ignore_errors=True)
        frames.mkdir(parents=True)
        # frames.mjs imports playwright: run it from this folder so it finds node_modules here
        shutil.copy(source / "frames.mjs", HERE / "_banner_frames.mjs")
        try:
            run([node, HERE / "_banner_frames.mjs", source / "banner.html", frames, theme, "20"], cwd=HERE)
        finally:
            (HERE / "_banner_frames.mjs").unlink(missing_ok=True)
        gif = WORK / f"banner-{theme}.gif"
        run([ffmpeg, "-y", "-loglevel", "error", "-framerate", "20", "-i", frames / "f%04d.png", "-vf",
             "fps=15,split[a][b];[a]palettegen=max_colors=40:stats_mode=diff[p];"
             "[b][p]paletteuse=dither=none:diff_mode=rectangle", "-loop", "0", gif])
        out = BRAND_OUT / f"banner-{theme}.gif"
        if gifsicle:
            run([gifsicle, "-O3", "--lossy=45", gif, "-o", out])
        else:
            shutil.copy(gif, out)
        print(f"{out.relative_to(REPO)}: {out.stat().st_size / 1024:.0f} KB")


# ------------------------------------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description="Record and convert the documentation clips.")
    ap.add_argument("names", nargs="*", help="clip names (default: all); 'banner' remakes the banner GIFs")
    ap.add_argument("--convert-only", action="store_true", help="only re-encode raw recordings in .cache/recordings/raw")
    ap.add_argument("--list", action="store_true", help="list the clips and stop")
    args = ap.parse_args()

    tapes = {p.stem: p for p in sorted((HERE / "tapes").glob("*.tape"))}
    clips = {p.stem: p for p in sorted((HERE / "clips").glob("*.mjs"))}
    if args.list:
        for n in tapes:
            print(f"tape  {n:22s} {tape_meta(tapes[n]).get('caption', '')}")
        for n in clips:
            print(f"clip  {n}")
        return 0
    wanted = args.names or [*tapes, *clips]
    if "banner" in wanted:
        make_banner()
        wanted = [n for n in wanted if n != "banner"]
        if not wanted:
            return 0
    unknown = [n for n in wanted if n not in tapes and n not in clips]
    if unknown:
        sys.exit(f"unknown clip(s): {', '.join(unknown)}; see --list")

    failed = []
    if not args.convert_only:
        tool("ffmpeg")
        prepare_site()
        for n in [n for n in wanted if n in tapes]:
            print(f"\n== tape {n}")
            record_tape(tapes[n])   # each tape starts from its own fresh copy
        browser = sorted((n for n in wanted if n in clips), key=lambda n: (n.startswith("editor"), n))  # Editor clips write files: last
        by_site: dict[str, list] = {}
        for n in browser:
            by_site.setdefault(clip_site(clips[n]), []).append(n)
        for k, (overlay, names) in enumerate(sorted(by_site.items())):
            site, port = (SITE, PORT) if not overlay else (WORK / f"site-{overlay}", PORT + 2 * k + 2)
            prepare_site(site, overlay)
            with Server(site, port):
                for n in names:
                    print(f"\n== clip {n}")
                    if not record_clip(clips[n], port):
                        failed.append(n)
    print()
    total = 0
    for n in [n for n in wanted if n not in failed]:
        r = convert(n)
        total += sum(v for k, v in r.items() if k in ("mp4", "webm", "jpg", "gif"))
        extra = f", gif {r['gif'] / 1024:.0f} KB" if "gif" in r else ""
        print(f"{n:22s} {r['seconds']:5.1f} s   mp4 {r['mp4'] / 1024:5.0f} KB   webm {r['webm'] / 1024:5.0f} KB"
              f"   poster {r['jpg'] / 1024:4.0f} KB{extra}")
    print(f"\nWritten to {CLIPS_OUT.relative_to(REPO)}/ ({total / 1048576:.1f} MB for these clips)")
    if failed:
        print(f"Not recorded (see the errors above): {', '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
