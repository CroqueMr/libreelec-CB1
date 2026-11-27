"""Kodi must return the inherited HDMI depth ceiling before releasing DRM."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_native_video_source import TREE, body


class MaxBpcLifecycleTests(unittest.TestCase):
    def test_restore_owned_limit_across_new_kodi_processes(self):
        source = (TREE / "xbmc/windowing/gbm/WinSystemGbm.cpp").read_text()
        destroy = body(source, "bool CWinSystemGbm::DestroyWindowSystem()")
        program = r"""
#include <cassert>
#include <cstdint>
#include <memory>
#include <optional>
#include <string_view>
#include <utility>
constexpr auto MAX_BPC = "max bpc";
constexpr int LOGDEBUG=0, LOGWARNING=1, LOGERROR=2;
struct CLog {
  template<class... T> static void Log(T&&...) {}
  template<class... T> static void LogF(T&&...) {}
};
struct Connector {
  std::optional<uint64_t>& wire;
  std::optional<uint64_t> accepted;
  std::optional<bool> immutable{false};
  std::optional<std::pair<uint64_t,uint64_t>> limits{std::pair<uint64_t,uint64_t>{8,16}};
  bool reject=false;
  int requests=0;
  auto GetPropertyValue(std::string_view) const { return accepted; }
  auto ReadPropertyValue(std::string_view) const { return wire; }
  auto IsPropertyImmutable(std::string_view) const { return immutable; }
  auto GetRangePropertyLimits(std::string_view) const { return limits; }
  bool SetProperty(std::string_view, uint64_t value) {
    ++requests;
    if (reject) return false;
    wire=accepted=value; return true;
  }
  void Commit(uint64_t value) { wire=accepted=value; }
};
struct DRM {
  explicit DRM(Connector* c) : connector(c) {}
  virtual ~DRM() = default;
  Connector* GetConnector() const { return connector; }
  Connector* connector;
};
struct CDRMAtomic : DRM { using DRM::DRM; };
struct Win {
  std::shared_ptr<DRM> m_DRM;
  std::optional<uint64_t> m_defaultMaxBpc;
  std::unique_ptr<int> m_libinput=std::make_unique<int>(1);
  bool DestroyWindowSystem() @DESTROY@
};
int main() {
  std::optional<uint64_t> wire=12;
  {
    Connector c{wire,wire}; Win w{std::make_shared<CDRMAtomic>(&c),wire};
    c.Commit(8); assert(w.DestroyWindowSystem()); assert(wire==12 && c.requests==1);
    assert(w.DestroyWindowSystem()); assert(c.requests==1);
  }
  // A new process starts with the same explicit choice, then stops before Auto.
  {
    Connector c{wire,wire}; Win w{std::make_shared<CDRMAtomic>(&c),wire};
    assert(w.m_defaultMaxBpc==12); c.Commit(8);
    assert(w.DestroyWindowSystem() && wire==12);
  }
  // Preserve a genuine driver default of 8; do not silently choose the range maximum.
  wire=8;
  {
    Connector c{wire,wire}; Win w{std::make_shared<CDRMAtomic>(&c),wire};
    c.Commit(12); assert(w.DestroyWindowSystem() && wire==8);
  }
  // Another owner changed the live value. Kodi must not overwrite it.
  wire=12;
  {
    Connector c{wire,wire}; Win w{std::make_shared<CDRMAtomic>(&c),wire};
    c.Commit(8); wire=10; assert(w.DestroyWindowSystem() && wire==10 && c.requests==0);
  }
  for (bool immutable : {false,true}) {
    wire=12;
    Connector c{wire,wire}; Win w{std::make_shared<CDRMAtomic>(&c),wire};
    c.immutable=immutable;
    if (immutable) c.Commit(8);
    assert(w.DestroyWindowSystem() && c.requests==0);
  }
  // No accepted write, no property, and legacy connectors must be left alone.
  wire=12;
  {
    Connector c{wire,wire}; Win w{std::make_shared<DRM>(&c),wire};
    c.Commit(8); assert(w.DestroyWindowSystem() && wire==8 && c.requests==0);
  }
  {
    Connector c{wire,{}}; Win w{std::make_shared<CDRMAtomic>(&c),{}};
    assert(w.DestroyWindowSystem() && c.requests==0);
  }
  wire=0;
  {
    Connector c{wire,wire}; Win w{std::make_shared<CDRMAtomic>(&c),wire};
    c.Commit(8); assert(w.DestroyWindowSystem() && wire==8 && c.requests==0);
  }
  wire=12;
  {
    Connector c{wire,wire}; Win w{std::make_shared<CDRMAtomic>(&c),wire};
    c.Commit(8); c.limits.reset(); assert(w.DestroyWindowSystem() && c.requests==0);
  }
  wire=12;
  {
    Connector c{wire,wire}; Win w{std::make_shared<CDRMAtomic>(&c),wire};
    c.Commit(8); c.reject=true;
    assert(w.DestroyWindowSystem() && wire==8 && c.requests==1);
  }
}
""".replace("@DESTROY@", destroy)
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "max-bpc-lifecycle"
            built = subprocess.run(["c++", "-std=c++20", "-x", "c++", "-", "-o", str(binary)],
                                   input=program, text=True, capture_output=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            subprocess.run([str(binary)], check=True)

    def test_a_new_drm_session_captures_a_fresh_default(self):
        source = (TREE / "xbmc/windowing/gbm/WinSystemGbm.cpp").read_text()
        init = body(source, "bool CWinSystemGbm::InitWindowSystem()")
        self.assertLess(init.index("m_defaultMaxBpc.reset();"),
                        init.index("m_DRM = std::make_shared<CDRMAtomic>()"))
