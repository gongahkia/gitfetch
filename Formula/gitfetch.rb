class Gitfetch < Formula
  include Language::Python::Virtualenv
  desc "Configurable GitHub profile fetch for the terminal"
  homepage "https://github.com/gongahkia/gitfetch"
  url "https://github.com/gongahkia/gitfetch/archive/refs/tags/2.0.tar.gz"
  sha256 "c0cc31a94da4543a9d83b43b63c5078f45876bd880a3d80b5070321981fd9050"
  license "MIT"
  depends_on "python@3.12"
  def install
    virtualenv_install_with_resources
  end
  test do
    assert_match "usage", shell_output("#{bin}/gitfetch --help")
  end
end
