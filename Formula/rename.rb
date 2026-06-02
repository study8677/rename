class Rename < Formula
  include Language::Python::Virtualenv

  desc "Auto-rename idle Claude Code, Codex, Cursor & Antigravity sessions"
  homepage "https://github.com/study8677/rename"
  url "https://github.com/study8677/rename/archive/refs/tags/v0.6.1.tar.gz"
  sha256 "43800bfb01b55a90fc1bee01c1d7b84c3b1d665c4cf1f3ef64a5e614c2c40d43"
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
