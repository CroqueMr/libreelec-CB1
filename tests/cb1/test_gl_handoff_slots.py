"""Exercise GL handoff ownership with two distinct selected and past pictures."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_native_video_source import TREE

def function(source, signature):
    start = source.index(signature)
    first = source.index("{", start)
    depth = 1
    for index in range(first + 1, len(source)):
        depth += (source[index] == "{") - (source[index] == "}")
        if depth == 0:
            return source[start:index + 1]
    raise ValueError(f"Unterminated method {signature}")


STUBS = r"""
#include <cstdio>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

#define HAVE_DVBRIDGE 1
constexpr int GL_BLEND=1, GL_SRC_ALPHA=2, GL_ONE_MINUS_SRC_ALPHA=3, VS_SCALINGMETHOD_MAX=4;
void glEnable(int) {}
void glDisable(int) {}
void glBlendFunc(int, int) {}
void glFlush() {}
struct VideoPicture {
  int id;
  struct { unsigned informationGeneration=7; } doviSourceInfo;
};
struct Shader { float alpha=0; void SetAlpha(float value) { alpha=value; } };
struct WinBase { virtual ~WinBase()=default; virtual bool UseLimitedColor() { return false; } };
struct FakeWindow : WinBase {
  enum class OrdinaryDraw { Deferred, Awaiting, Attempted, Drawn };
  bool m_dvOrdinaryFrame=false, m_dvStopPending=false;
  std::shared_ptr<const VideoPicture> m_deferredOrdinaryPicture;
  OrdinaryDraw m_deferredOrdinaryDraw=OrdinaryDraw::Deferred;
  void DeferOrdinaryVideo(std::shared_ptr<const VideoPicture>);
  void MarkDeferredOrdinaryVideoAttempted(const VideoPicture&);
  void MarkDeferredOrdinaryVideoDrawn(const VideoPicture&);
  HAS_RECEIPT
  // The test controls subsequent GUI frames and the outcome of the KMS boundary.
  void nextFrame() { m_deferredOrdinaryDraw=OrdinaryDraw::Awaiting; }
  bool flip(bool accept, int stagedSource) {
    if (!m_deferredOrdinaryPicture || m_deferredOrdinaryDraw!=OrdinaryDraw::Drawn)
      throw std::runtime_error("attempted a flip without a newly drawn retained picture");
    if (stagedSource!=m_deferredOrdinaryPicture->id)
      throw std::runtime_error("published source side data belongs to a different picture");
    if (accept) { m_deferredOrdinaryPicture.reset(); m_dvOrdinaryFrame=false; }
    return accept;
  }
};
namespace KODI::WINDOWING::GBM { using CWinSystemGbmDVContext=FakeWindow; }
struct CServiceBroker {
  static FakeWindow* GetWinSystem() { static FakeWindow window; return &window; }
};
struct Sample { int id; float alpha; };
struct Renderer {
  struct Slot { std::shared_ptr<const VideoPicture> doviSourcePicture; };
  Slot m_buffers[2]={{std::make_shared<VideoPicture>(VideoPicture{0,{7}})},
                     {std::make_shared<VideoPicture>(VideoPicture{1,{7}})}};
  int m_iYUVRenderBuffer=0, m_scalingMethodGui=0;
  bool m_frameRendered=false, m_hdrFboActive=false, m_dvRequested=false;
  bool m_fullRange=true, m_reloadShaders=false, requestNative=false;
  std::optional<bool> m_pendingHdrFbo;
  Shader shader;
  Shader* m_pYUVShader=&shader;
  Shader* m_pVideoFilterShader=nullptr;
  std::vector<Sample> attempts, pixels;
  void RenderUpdate(int,int,bool,unsigned int,unsigned int);
  bool ValidateRenderer() { return true; }
  void UpdateActiveArea(int) {}
  void ManageRenderArea() {}
  void DrawBlackBars() {}
  void ClearBackBuffer() { pixels.clear(); }
  void VerifyGLState() {}
  bool Render(unsigned, int slot) {
    FakeWindow& window=*CServiceBroker::GetWinSystem();
    const auto& picture=m_buffers[slot].doviSourcePicture;
    attempts.push_back({picture->id,shader.alpha});
    if (requestNative && m_dvRequested) {
      requestNative=false;
      m_dvRequested=false;
      window.m_dvOrdinaryFrame=true;
      window.DeferOrdinaryVideo(picture);
      m_pendingHdrFbo=false;
      return false;
    }
    if (window.m_dvOrdinaryFrame && window.m_deferredOrdinaryPicture.get()!=picture.get())
      return false;
    pixels.push_back({picture->id,shader.alpha});
    window.MarkDeferredOrdinaryVideoDrawn(*picture);
    return true;
  }
  void frame() {
    attempts.clear();
    pixels.clear();
    RenderUpdate(1,0,true,0,255);  // B is selected, A is the previous catch-up slot.
  }
  int stagedSource() const { return m_frameRendered ? m_buffers[1].doviSourcePicture->id : -1; }
};
"""

SCENARIOS = r"""
void require(bool ok, const char* message) {
  if (!ok) throw std::runtime_error(message);
}
void assertPrimary(const Renderer& r) {
  require(r.attempts.size()==1 && r.attempts[0].id==1, "expected selected B as the sole draw attempt");
  require(r.pixels.size()==1 && r.pixels[0].id==1 && r.pixels[0].alpha==1.0f,
          "expected one full-opacity draw of B");
  require(r.stagedSource()==1, "RenderManager would not stage B's source side data");
}
void scenario(const std::string& name) {
  Renderer r;
  auto& win=*CServiceBroker::GetWinSystem();
  if (name=="native-sdr" || name=="native-hdr") {
    r.m_hdrFboActive=name=="native-hdr";  // Kodi's native HDR compositor also sets this bit.
    r.frame();
    require(r.attempts.size()==2 && r.attempts[0].id==0 && r.attempts[1].id==1,
            "ordinary GL two-slot order changed");
    require(r.pixels.size()==2 && r.pixels[0].alpha==1.0f &&
            r.pixels[1].alpha<r.pixels[0].alpha && r.m_frameRendered,
            "ordinary GL blend or success status changed");
    require(!win.m_deferredOrdinaryPicture, "ordinary playback acquired a CB1 handoff");
    return;
  }
  if (name=="handoff") {
    r.m_hdrFboActive=r.m_dvRequested=r.requestNative=true;
    r.frame();
    require(win.m_deferredOrdinaryPicture==r.m_buffers[1].doviSourcePicture,
            "handoff retained the past slot A instead of the selected slot B");
    require(r.attempts.size()==1 && !r.m_frameRendered && r.pixels.empty(),
            "the mixed-owner detection frame must not draw video");
    require(r.m_pendingHdrFbo.has_value() && !*r.m_pendingHdrFbo, "expected pending ordinary layer");
    r.m_hdrFboActive=false;  // Next FrameMove applied the admitted GUI owner.
    win.nextFrame();
    r.frame();
    assertPrimary(r);
    require(!r.m_pendingHdrFbo, "RenderUpdate did not consume the applied layer");
    require(!win.flip(false,r.stagedSource()), "expected the first KMS attempt to be rejected");
  } else if (name=="retained-retry") {
    // Enter directly after a rejected commit so this case can expose an independent failure.
    win.m_dvOrdinaryFrame=true;
    win.DeferOrdinaryVideo(r.m_buffers[1].doviSourcePicture);
  } else {
    throw std::runtime_error("unknown scenario");
  }
  require(!r.m_pendingHdrFbo && !r.m_hdrFboActive && !r.m_dvRequested &&
          win.m_deferredOrdinaryPicture==r.m_buffers[1].doviSourcePicture,
          "the exact receipt must be the only outstanding handoff state");
  win.nextFrame();
  r.frame();
  assertPrimary(r);
  require(win.flip(true,r.stagedSource()) && !win.m_deferredOrdinaryPicture,
          "accepted presentation failed to retire the handoff");
  r.frame();
  require(r.attempts.size()==2 && r.attempts[0].id==0 && r.attempts[1].id==1,
          "ordinary catch-up blending did not resume after acceptance");
}
int main(int argc, char** argv) {
  try {
    if (argc!=2) throw std::runtime_error("expected one scenario name");
    scenario(argv[1]);
    return 0;
  } catch (const std::exception& error) {
    std::fprintf(stderr,"%s\n",error.what()); return 1;
  }
}
"""



class GLHandoffSlots(unittest.TestCase):
    def test_selected_picture_owns_handoff_and_retry(self):
        graphics = "xbmc/windowing/gbm/WinSystemGbmGLContext"
        renderer = (TREE / "xbmc/cores/VideoPlayer/VideoRenderers/LinuxRendererGL.cpp").read_text()
        context = (TREE / (graphics + ".cpp")).read_text()
        header = (TREE / (graphics + ".h")).read_text()
        receipt = "bool HasDeferredOrdinaryVideo() const"
        code = STUBS.replace("HAS_RECEIPT", function(header, receipt) if receipt in header else "")
        for method in ("DeferOrdinaryVideo", "MarkDeferredOrdinaryVideoAttempted",
                       "MarkDeferredOrdinaryVideoDrawn"):
            signature = "void CWinSystemGbmGLContext::" + method + "("
            code += "\n" + function(context, signature).replace("CWinSystemGbmGLContext::", "FakeWindow::")
        code += "\n" + function(renderer, "void CLinuxRendererGL::RenderUpdate(").replace(
            "CLinuxRendererGL::", "Renderer::") + "\n" + SCENARIOS
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "slots.cpp"
            binary = Path(temporary) / "slots"
            source.write_text(code, encoding="utf-8")
            subprocess.run(["c++", "-std=c++17", str(source), "-o", str(binary)], check=True)
            for case in ("handoff", "retained-retry", "native-sdr", "native-hdr"):
                with self.subTest(case=case):
                    subprocess.run([str(binary), case], check=True)
