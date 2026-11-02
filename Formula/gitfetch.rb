class Gitfetch < Formula
  include Language::Python::Virtualenv

  desc "Neofetch-style profiles for six Git hosting providers"
  homepage "https://github.com/gongahkia/gitfetch"
  url "https://github.com/gongahkia/gitfetch/archive/refs/tags/2.0.tar.gz"
  sha256 "c0cc31a94da4543a9d83b43b63c5078f45876bd880a3d80b5070321981fd9050"
  license "MIT"
  depends_on "cmake" => :build
  depends_on "pkgconf" => :build
  depends_on "freetype"
  depends_on "jpeg-turbo"
  depends_on "python@3.12"
  depends_on "webp"
  depends_on "zlib-ng-compat"

  resource "certifi" do
    url "https://files.pythonhosted.org/packages/fd/11/b524cbd9bbdaca58608e4cf4053fd463417549e1959fa8d3aa18319f9555/certifi-2026.10.23.tar.gz"
    sha256 "a9895e6e2758b371e0545e321a3a8fd1fcfd9829ada8824a936dfb16aaaf36cd"
  end

  resource "charset-normalizer" do
    url "https://files.pythonhosted.org/packages/83/2d/5fd176ceb9b2fc619e63405525573493ca23441330fcdaee6bef9460e924/charset_normalizer-3.4.3.tar.gz"
    sha256 "6fce4b8500244f6fcb71465d4a4930d132ba9ab8e71a7859e6a5d59851068d14"
  end

  resource "idna" do
    url "https://files.pythonhosted.org/packages/f5/08/8eea9d4b8302028f3abb2c0813953f7aec26d33b7a8960ed760e65ff29fa/idna-3.20.tar.gz"
    sha256 "a7db850025b95ded1eae8a46181a1a6c56c92c96f0e2b005d9ff8dc0210cab44"
  end

  resource "pillow" do
    url "https://files.pythonhosted.org/packages/ce/a4/9cc30690a394a8305e8be4c9036aa16d0dfddadd09079860b582f562496d/pillow-13.0.0.tar.gz"
    sha256 "cdcd1ba258178f7356d74170c9a81ba4eab6a5d55748bc402a5a2a6fe6be3510"
  end

  resource "requests" do
    url "https://files.pythonhosted.org/packages/ac/c3/e2a2b89f2d3e2179abd6d00ebd70bff6273f37fb3e0cc209f48b39d00cbf/requests-2.34.2.tar.gz"
    sha256 "f288924cae4e29463698d6d60bc6a4da69c89185ad1e0bcc4104f584e960b9ed"
  end

  resource "urllib3" do
    url "https://files.pythonhosted.org/packages/e3/05/b17359e1cefb4f909b5e40b1b90a496d987258916dbbf88e842c729f510e/urllib3-2.8.0.tar.gz"
    sha256 "63bf2ead4c879426ebf22ef2a781eeb4aa3b4ae798a0435506f8687fd5bb9b63"
  end

  resource "wcwidth" do
    url "https://files.pythonhosted.org/packages/69/4a/82d61476a1ccc20d43d0805724c5de4baa4971131a8db1816705ef53fe16/wcwidth-0.9.3.tar.gz"
    sha256 "dfe7cfbd4cb59db9fe0931bd6091ab4a95b3acc5d56bfb50fa9fef0ccba5dc5c"
  end

  def install
    virtualenv_install_with_resources system_site_packages: false
  end
  test do
    assert_match "usage", shell_output("#{bin}/gitfetch --help")
    system libexec/"bin/python", "-c", <<~PYTHON
      import io
      from importlib.resources import files
      from pathlib import Path
      from PIL import Image, ImageFont, features
      import sys
      assert "include-system-site-packages = false" in (Path(sys.prefix) / "pyvenv.cfg").read_text()
      assert all(features.check(name) for name in ("jpg", "zlib", "webp", "freetype2"))
      font = files("gitfetch") / "assets/fonts/DejaVuSans.ttf"
      ImageFont.truetype(str(font), 18).getbbox("Gitfetch e\\u0301 \\u6f22\\u5b57")
      image = Image.new("RGBA", (24, 12), (20, 40, 60, 128))
      for format_name in ("PNG", "WEBP"):
          output = io.BytesIO()
          image.save(output, format_name, lossless=True)
          output.seek(0)
          decoded = Image.open(output).convert("RGBA")
          assert decoded.size == image.size
          assert decoded.getpixel((0, 0))[3] == 128
      output = io.BytesIO()
      image.convert("RGB").save(output, "JPEG")
      output.seek(0)
      assert Image.open(output).size == image.size
    PYTHON
  end
end
