# caption: Copy a figure from a starter, test it, and see where every figure is used.
Output raw/figure-cli.mp4
Set Shell "bash"
Set FontFamily "Menlo"
Set FontSize 20
Set Width 1280
Set Height 600
Set Padding 28
Set Framerate 25
Set TypingSpeed 45ms
Set CursorBlink false
Set Theme { "name": "Bazinga paper", "black": "#1D1A15", "red": "#B8241A", "green": "#2F7D32", "yellow": "#A36A00", "blue": "#0F52BA", "magenta": "#7A3E9D", "cyan": "#1F6F8B", "white": "#E4DBC9", "brightBlack": "#655D51", "brightRed": "#D2362A", "brightGreen": "#3C9A40", "brightYellow": "#C08A10", "brightBlue": "#3B74CC", "brightMagenta": "#9B59B6", "brightCyan": "#2A8FB0", "brightWhite": "#FBF7EC", "background": "#FBF7EC", "foreground": "#1D1A15", "selection": "#E4DBC9", "cursor": "#0F52BA" }

# Hidden setup: a fresh copy of the example site, the template's Python first on PATH, a short prompt.
Hide
Type 'cd site && export PATH="$BAZINGA_BIN:$PATH" PS1="\[\e[34m\]my-site\[\e[0m\] $ " && clear'
Enter
Sleep 500ms
Show
Type "python -m bazinga figure starters | head -n 8"
Sleep 400ms
Enter
Sleep 2.5s
Type "python -m bazinga figure new my_plot --from slider_plot"
Sleep 400ms
Enter
Sleep 1.5s
Type "python -m bazinga figure test my_plot"
Sleep 400ms
Enter
Sleep 4s
