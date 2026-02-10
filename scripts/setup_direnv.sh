#!/bin/bash
# One-command setup for direnv + AWS profile enforcement

set -e

echo "🚀 Setting up direnv for AWS Profile Management"
echo "================================================"

# Check if direnv is installed
if ! command -v direnv &> /dev/null; then
    echo "❌ direnv not found. Installing..."
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command -v brew &> /dev/null; then
            brew install direnv
        else
            echo "❌ Homebrew not found. Install from: https://brew.sh"
            exit 1
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        if command -v apt-get &> /dev/null; then
            sudo apt-get update && sudo apt-get install -y direnv
        elif command -v yum &> /dev/null; then
            sudo yum install -y direnv
        else
            echo "❌ Package manager not found. Install direnv manually: https://direnv.net"
            exit 1
        fi
    else
        echo "❌ Unsupported OS: $OSTYPE"
        exit 1
    fi
    
    echo "✅ direnv installed"
else
    echo "✅ direnv already installed: $(which direnv)"
fi

# Detect shell
SHELL_NAME=$(basename "$SHELL")
echo "✅ Detected shell: $SHELL_NAME"

# Add hook to shell config
SHELL_CONFIG=""
HOOK_LINE=""

case "$SHELL_NAME" in
    zsh)
        SHELL_CONFIG="$HOME/.zshrc"
        HOOK_LINE='eval "$(direnv hook zsh)"'
        ;;
    bash)
        SHELL_CONFIG="$HOME/.bashrc"
        HOOK_LINE='eval "$(direnv hook bash)"'
        ;;
    fish)
        SHELL_CONFIG="$HOME/.config/fish/config.fish"
        HOOK_LINE='direnv hook fish | source'
        ;;
    *)
        echo "⚠️  Unknown shell: $SHELL_NAME"
        echo "   Please add direnv hook manually"
        echo "   See: https://direnv.net/docs/hook.html"
        SHELL_CONFIG=""
        ;;
esac

# Add hook if not already present
if [ -n "$SHELL_CONFIG" ]; then
    if grep -q "direnv hook" "$SHELL_CONFIG" 2>/dev/null; then
        echo "✅ direnv hook already in $SHELL_CONFIG"
    else
        echo "Adding direnv hook to $SHELL_CONFIG..."
        echo "" >> "$SHELL_CONFIG"
        echo "# direnv hook (for automatic AWS profile management)" >> "$SHELL_CONFIG"
        echo "$HOOK_LINE" >> "$SHELL_CONFIG"
        echo "✅ direnv hook added to $SHELL_CONFIG"
    fi
fi

# Allow .envrc for this repo
echo ""
echo "Allowing .envrc for this repository..."
cd "$(dirname "$0")/.."
direnv allow

echo ""
echo "✅ Setup complete!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 NEXT STEPS:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1. Restart your terminal (or run: source $SHELL_CONFIG)"
echo ""
echo "2. Navigate to this repo:"
echo "   cd $(pwd)"
echo ""
echo "   You should see:"
echo "   ✅ AWS Profile set to: gghouse (Account: 343881458651)"
echo ""
echo "3. Login to AWS SSO:"
echo "   aws sso login --profile gghouse"
echo ""
echo "4. Verify setup:"
echo "   aws sts get-caller-identity"
echo "   (Should show Account: 343881458651)"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🎉 direnv will now automatically set AWS_PROFILE=gghouse"
echo "   whenever you cd into this repository!"
echo ""
