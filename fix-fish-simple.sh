#!/bin/bash
# Simple fix for fish shell - just remove the problematic config

# Remove the oh-my-posh fish config that causes issues
sed -i '/oh-my-posh init fish/d' /home/ollama/.config/fish/config.fish 2>/dev/null || true

# Add a simple prompt for fish that doesn't use the problematic command
cat >> /home/ollama/.config/fish/config.fish << 'EOF'

# Simple colored prompt for fish
function fish_prompt
    set_color cyan
    echo -n (date "+%H:%M:%S")
    set_color normal
    echo -n " | "
    set_color yellow
    echo -n (pwd | sed "s|$HOME|~|")
    set_color normal
    echo -n " ❯ "
end
EOF