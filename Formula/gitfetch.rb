class Gitfetch < Formula
  include Language::Python::Virtualenv
  desc "Configurable GitHub profile fetch for the terminal"
  homepage "https://github.com/gongahkia/gitfetch"
  url "https://github.com/gongahkia/gitfetch/archive/refs/tags/2.0.tar.gz"
  sha256 "c0cc31a94da4543a9d83b43b63c5078f45876bd880a3d80b5070321981fd9050"
  license "MIT"
  depends_on "python@3.12"

  resource "certifi" do
    url "https://files.pythonhosted.org/packages/source/c/certifi/certifi-2025.8.3.tar.gz"
    sha256 "e564105f78ded564e3ae7c923924435e1daa7463faeab5bb932bc53ffae63407"
  end

  resource "charset-normalizer" do
    url "https://files.pythonhosted.org/packages/source/c/charset_normalizer/charset_normalizer-3.4.3.tar.gz"
    sha256 "6fce4b8500244f6fcb71465d4a4930d132ba9ab8e71a7859e6a5d59851068d14"
  end

  resource "idna" do
    url "https://files.pythonhosted.org/packages/source/i/idna/idna-3.10.tar.gz"
    sha256 "12f65c9b470abda6dc35cf8e63cc574b1c52b11df2c86030af0ac09b01b13ea9"
  end

  resource "pillow" do
    url "https://files.pythonhosted.org/packages/source/p/pillow/pillow-11.3.0.tar.gz"
    sha256 "3828ee7586cd0b2091b6209e5ad53e20d0649bbe87164a459d0676e035e8f523"
  end

  resource "requests" do
    url "https://files.pythonhosted.org/packages/source/r/requests/requests-2.32.5.tar.gz"
    sha256 "dbba0bac56e100853db0ea71b82b4dfd5fe2bf6d3754a8893c3af500cec7d7cf"
  end

  resource "urllib3" do
    url "https://files.pythonhosted.org/packages/source/u/urllib3/urllib3-2.5.0.tar.gz"
    sha256 "3fc47733c7e419d4bc3f6b3dc2b4f890bb743906a30d56ba4a5bfa4bbff92760"
  end

  def install
    virtualenv_install_with_resources
  end
  test do
    assert_match "usage", shell_output("#{bin}/gitfetch --help")
  end
end
