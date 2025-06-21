#!/bin/bash
# Fix fish shell compatibility with oh-my-posh

# Create a wrapper script for fish that filters out the problematic option
cat > /usr/local/bin/fish-omp-fix << 'EOF'
#!/bin/bash
# This script fixes the oh-my-posh fish integration

# Create a fixed version of the oh-my-posh fish init
if [ -f ~/.config/fish/config.fish ]; then
    # Remove the problematic line and create a simpler config
    grep -v "oh-my-posh init fish" ~/.config/fish/config.fish > ~/.config/fish/config.fish.tmp
    mv ~/.config/fish/config.fish.tmp ~/.config/fish/config.fish
    
    # Add a simpler oh-my-posh init that works with older fish
    echo '# Oh-my-posh initialization' >> ~/.config/fish/config.fish
    echo 'set -gx POSH_THEME https://raw.githubusercontent.com/JanDeDobbeleer/oh-my-posh/main/themes/kushal.omp.json' >> ~/.config/fish/config.fish
    echo 'function fish_prompt' >> ~/.config/fish/config.fish
    echo '    oh-my-posh print primary --config $POSH_THEME --shell fish' >> ~/.config/fish/config.fish
    echo 'end' >> ~/.config/fish/config.fish
    echo '' >> ~/.config/fish/config.fish
    echo 'function fish_right_prompt' >> ~/.config/fish/config.fish
    echo '    oh-my-posh print right --config $POSH_THEME --shell fish' >> ~/.config/fish/config.fish
    echo 'end' >> ~/.config/fish/config.fish
fi

# Start fish normally
exec /usr/bin/fish "$@"
EOF

chmod +x /usr/local/bin/fish-omp-fix

# Create aliases for all users
echo "alias fish='/usr/local/bin/fish-omp-fix'" >> /etc/bash.bashrc