class Gitfetch < Formula
  include Language::Python::Virtualenv
  desc "GitHub user info displayed as ASCII art in terminal"
  homepage "https://github.com/gongahkia/gitfetch"
  url "https://github.com/gongahkia/gitfetch/archive/refs/tags/v2.0.0.tar.gz"
  sha256 "" # update after release
  license "MIT"
  depends_on "python@3.12"
  def install
    virtualenv_install_with_resources
  end
  test do
    assert_match "usage", shell_output("#{bin}/gitfetch --help")
  end
end
