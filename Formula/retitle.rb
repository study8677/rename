class Retitle < Formula
  include Language::Python::Virtualenv

  desc "Auto-rename idle Claude Code, Codex, Cursor & Antigravity sessions"
  homepage "https://github.com/study8677/retitle"
  url "https://github.com/study8677/retitle/archive/refs/tags/v0.6.0.tar.gz"
  sha256 "d1927b734ff5271704eb1efe93ecd3bf7a932734b264e43dbd8d0e651763a143"
  license "MIT"
  head "https://github.com/study8677/retitle.git", branch: "main"

  depends_on "python@3.12"

  def install
    virtualenv_install_with_resources
  end

  service do
    run [opt_bin/"retitle", "run"]
    keep_alive true
    log_path var/"log/retitle.log"
    error_log_path var/"log/retitle.log"
    working_dir HOMEBREW_PREFIX
  end

  test do
    assert_match "retitle #{version}", shell_output("#{bin}/retitle --version")
    # `status` shouldn't crash on a fresh machine with no AI tools installed.
    assert_match(/retitle/, shell_output("#{bin}/retitle status"))
  end
end
