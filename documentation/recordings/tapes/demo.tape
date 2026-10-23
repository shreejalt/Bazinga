# caption: Bazinga in twenty seconds: build the example site, add a figure, test it, and serve it.
# gif: true
# gif_width: 1200
# gif_seconds: 20
# The README's demo. Regenerate it with: python documentation/recordings/make.py demo
Output raw/demo.mp4
Set Shell "bash"
Set FontFamily "Menlo"
Set FontSize 18
Set Width 1200
Set Height 760
Set Padding 16
Set Framerate 16
Set TypingSpeed 35ms
Set CursorBlink false
Set Theme { "name": "Bazinga paper", "black": "#1D1A15", "red": "#B8241A", "green": "#2F7D32", "yellow": "#A36A00", "blue": "#0F52BA", "magenta": "#7A3E9D", "cyan": "#1F6F8B", "white": "#E4DBC9", "brightBlack": "#655D51", "brightRed": "#D2362A", "brightGreen": "#3C9A40", "brightYellow": "#C08A10", "brightBlue": "#3B74CC", "brightMagenta": "#9B59B6", "brightCyan": "#2A8FB0", "brightWhite": "#FBF7EC", "background": "#FBF7EC", "foreground": "#1D1A15", "selection": "#E4DBC9", "cursor": "#0F52BA" }

# Hidden setup: a throwaway copy of the template in a temporary folder, the template's Python first on PATH.
Hide
Type 'D="$(mktemp -d)/my-site" && cp -R site "$D" && cd "$D" && export PATH="$BAZINGA_BIN:$PATH" PS1="\[\e[34m\]my-site\[\e[0m\] \$ " && clear'
Enter
Sleep 1s
Show

Type "python -m bazinga build"
Enter
Sleep 2s
Type "python -m bazinga figure new my_plot --from slider_plot"
Enter
Sleep 1.5s
Type "python -m bazinga figure test my_plot"
Enter
Sleep 2.5s
Type "python -m bazinga serve"
Enter
Sleep 4s
Ctrl+C
Sleep 1s
