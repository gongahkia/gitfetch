#!/bin/bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends build-essential ca-certificates curl file git procps
useradd -m -s /bin/bash linuxbrew
mkdir -p /home/linuxbrew/.linuxbrew
chown -R linuxbrew:linuxbrew /home/linuxbrew
runuser -u linuxbrew -- git clone --depth=1 https://github.com/Homebrew/brew /home/linuxbrew/.linuxbrew/Homebrew
runuser -u linuxbrew -- mkdir -p /home/linuxbrew/.linuxbrew/bin
runuser -u linuxbrew -- ln -s ../Homebrew/bin/brew /home/linuxbrew/.linuxbrew/bin/brew
tap=/home/linuxbrew/.linuxbrew/Homebrew/Library/Taps/gitfetch/homebrew-security/Formula
mkdir -p "$tap"
cp /production.rb "$tap/gitfetch.rb"
archive=/candidate/gitfetch-2.0.0.tar.gz
digest=$(sha256sum "$archive" | cut -d' ' -f1)
# Only the disposable copy gets the local archive; production bytes stay read-only.
sed -i "0,/^  url /s|^  url .*|  url \"file://$archive\"|" "$tap/gitfetch.rb"
sed -i "0,/^  sha256 /s|^  sha256 .*|  sha256 \"$digest\"|" "$tap/gitfetch.rb"
chown -R linuxbrew:linuxbrew /home/linuxbrew/.linuxbrew/Homebrew/Library/Taps/gitfetch
runuser -u linuxbrew -- env HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_ANALYTICS=1 bash -c '
set -euo pipefail
eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"
brew --version
brew trust gitfetch/security
brew install --build-from-source gitfetch/security/gitfetch
brew test gitfetch/security/gitfetch
brew list --versions
gitfetch --version
gitfetch --help
python_path="$(brew --prefix gitfetch/security/gitfetch)/libexec/bin/python"
"$python_path" -c "import sys,importlib.metadata as m; print(sys.version); print({d.metadata[\"Name\"]:d.version for d in m.distributions()})"
'
