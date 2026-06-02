class Rename < Formula
  include Language::Python::Virtualenv

  desc "Keep your AI coding sessions named after what they actually became"
  homepage "https://github.com/study8677/rename"
  url "https://github.com/study8677/rename/archive/refs/tags/v1.0.0.tar.gz"
  sha256 "7442920caf0d9a8f20a0453104682e275a11fae4b276993495e3553b7b65125d"
  license "MIT"
  head "https://github.com/study8677/rename.git", branch: "main"

  depends_on "python@3.12"

  def install
    virtualenv_install_with_resources
  end

  service do
    run [opt_bin/"rename", "run"]
    keep_alive true
    log_path var/"log/rename.log"
    error_log_path var/"log/rename.log"
    working_dir HOMEBREW_PREFIX
  end

  test do
    assert_match "rename #{version}", shell_output("#{bin}/rename --version")
    # `status` shouldn't crash on a fresh machine with no AI tools installed.
    assert_match(/rename/, shell_output("#{bin}/rename status"))
  end
end
