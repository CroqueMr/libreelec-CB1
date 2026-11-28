"""Windowed composited video must have a visible, frame-local presentation owner."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_native_video_source import TREE, body


class WindowedHDRVideoTests(unittest.TestCase):
    def test_single_visible_owner_and_fitted_aperture(self):
        program = r"""
#include "guilib/WindowedVideoComposite.h"
#include <cassert>
#include <initializer_list>
int main()
{
  CWindowedVideoComposite frame;
  const CRect view(0, 0, 100, 100), clip(10, 10, 90, 90), fitted(0, 20, 100, 80);
  frame.BeginFrame(false);
  frame.BeginControl(view, clip, 0.25f, 255);
  assert(!frame.Queue(fitted) && !frame.HasOwner());
  frame.BeginFrame(true);
  assert(!frame.HasOwner() && !frame.Queue(fitted));
  frame.BeginControl(view, clip, 0.25f, 0);
  assert(!frame.Queue(fitted));
  frame.EndControl();
  frame.BeginControl(view, clip, 0.25f, 255);
  const auto mask = frame.Queue(fitted);
  assert(mask && *mask == CRect(10, 20, 90, 80));
  frame.EndControl();
  assert(frame.HasOwner());
  // An invisible or fully clipped control cannot steal the visible target.
  frame.BeginControl(CRect(200, 200, 300, 300), CRect(200, 200, 300, 300), 0.75f, 127);
  assert(!frame.Queue(fitted));
  frame.EndControl();
  auto owner = frame.TakeOwner();
  assert(owner && owner->view == view && owner->clip == clip && owner->opacity == 255);
  assert(!frame.HasOwner() && !frame.TakeOwner());
  // A single late presentation may create exactly one aperture, even for
  // disjoint or overlapping controls drawn later in the same GUI frame.
  for (const CRect next : {CRect(30, 30, 60, 60), CRect(200, 200, 300, 300)})
  {
    frame.BeginFrame(true);
    frame.BeginControl(view, clip, 0.25f, 255);
    assert(frame.Queue(fitted)); frame.EndControl();
    frame.BeginControl(next, next, 0.75f, 127);
    assert(!frame.Queue(next)); frame.EndControl();
    owner = frame.TakeOwner();
    assert(owner && owner->view == view && owner->clip == clip && owner->depth == 0.25f);
    assert(!frame.TakeOwner());
  }
  // The legacy full-screen background can be covered by a real dialog. Its
  // opaque aperture supersedes the old hole, which is entirely covered.
  for (const CRect cover : {CRect(10, 20, 90, 80), fitted, CRect(0, 0, 100, 100)})
  {
    frame.BeginFrame(true);
    frame.BeginControl(view, clip, 0.25f, 255);
    assert(frame.Queue(fitted)); frame.EndControl();
    frame.BeginControl(cover, cover, 0.75f, 255);
    assert(frame.Queue(cover)); frame.EndControl();
    owner=frame.TakeOwner();
    assert(owner && owner->view==cover && owner->depth==0.75f);
  }
  // A faded upper control must not compound transparency in the old hole.
  frame.BeginFrame(true);
  frame.BeginControl(view, clip, 0.25f, 255); assert(frame.Queue(fitted)); frame.EndControl();
  frame.BeginControl(view, view, 0.75f, 127); assert(!frame.Queue(view)); frame.EndControl();
  owner=frame.TakeOwner();assert(owner && owner->depth==0.25f);
  // A partly overlapping opaque aperture leaves an orphan and cannot take over.
  frame.BeginFrame(true);
  frame.BeginControl(view, clip, 0.25f, 255); assert(frame.Queue(fitted)); frame.EndControl();
  const CRect overlap(40,40,120,100);
  frame.BeginControl(overlap, overlap, 0.75f, 255);assert(!frame.Queue(overlap));frame.EndControl();
  owner=frame.TakeOwner();assert(owner && owner->depth==0.25f);
  // If the earlier control is clipped, a dialog-only control can own the frame.
  frame.BeginFrame(true);
  frame.BeginControl(view, CRect(200, 200, 300, 300), 0.25f, 255);
  assert(!frame.Queue(fitted)); frame.EndControl();
  const CRect dialog(30, 30, 60, 60);
  frame.BeginControl(dialog, dialog, 0.75f, 127);
  assert(frame.Queue(dialog)); frame.EndControl();
  owner=frame.TakeOwner();
  assert(owner && owner->view == dialog && owner->opacity == 127);
  frame.BeginControl(view, clip, 0.25f, 255); assert(frame.Queue(fitted));
  frame.BeginFrame(true); assert(!frame.HasOwner() && !frame.Queue(fitted));
}
"""
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "windowed-hdr"
            built = subprocess.run(["c++", "-std=c++20", "-I", str(TREE / "xbmc"),
                                    "-x", "c++", "-", "-o", str(binary)],
                                   input=program, text=True, capture_output=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            subprocess.run([str(binary)], check=True)

    def test_video_draw_is_selected_from_gui_pass_not_all_dialogs(self):
        gui = TREE / "xbmc/guilib"
        app = (TREE / "xbmc/application/Application.cpp").read_text()
        manager = (gui / "GUIWindowManager.cpp").read_text()
        control = (gui / "GUIVideoControl.cpp").read_text()
        renderer = (TREE / "xbmc/cores/VideoPlayer/VideoRenderers/RenderManager.cpp").read_text()
        render = body(app, "void CApplication::Render()")
        self.assertLess(render.index("BeginFrameGuiComposite(guiWillRender)"),
                        render.index("GetWindowedVideoComposite().BeginFrame("))
        late = body(manager, "void CGUIWindowManager::RenderEx()")
        self.assertLess(late.index("pWindow->RenderEx()"), late.index("TakeOwner()"))
        self.assertIn("appPlayer->Render(false, 255, false)", late)
        self.assertNotIn("m_activeDialogs", late)
        draw = body(control, "void CGUIVideoControl::Render()")
        self.assertIn("BeginControl(", draw)
        self.assertIn("EndControl()", draw)
        self.assertIn("IsRenderingVideoLayer()", draw)
        late_control = body(control, "void CGUIVideoControl::RenderEx()")
        # A slideshow with no owner still uses its pre-existing late-video path.
        self.assertIn("appPlayer->Render(false, 255, false)", late_control)
        self.assertNotIn("GetWindowedVideoComposite().Active()", late_control)
        self.assertLess(draw.index("graphics.ClipRect(local, uv)"), draw.index("graphics.SetTransform(mat"))
        present = body(renderer, "void CRenderManager::Render(bool clear, DWORD flags, DWORD alpha, bool gui)")
        self.assertIn("!gui && windowedVideo.HasOwner()", present)
        self.assertLess(present.index("m_pRenderer->GetVideoRect(src, dst, view);", present.index("if (gui)")),
                        present.index("DrawVideoAperture("))
        self.assertLess(present.index("DrawVideoAperture("), present.index("m_overlays.Render(m_presentsource);", present.index("DrawVideoAperture(")))
        for api in ("GL", "GLES"):
            texture = (gui / f"GUITexture{api}.cpp").read_text()
            self.assertIn("GL_ZERO, GL_ONE_MINUS_SRC_ALPHA", texture)
            self.assertIn("DrawVideoAperture", texture)

    def test_gl_aperture_uses_control_depth_for_opaque_and_translucent_draws(self):
        texture = (TREE / "xbmc/guilib/GUITextureGL.cpp").read_text()
        shader = (TREE / "xbmc/rendering/gl/RenderSystemGL.cpp").read_text()
        aperture = body(texture, "void CGUITextureGL::DrawVideoAperture(")
        self.assertIn("depth, false, true", aperture)
        self.assertIn("depth, true, true", aperture)
        self.assertIn("aperture ? ShaderMethodGL::SM_VIDEO_APERTURE", texture)
        self.assertIn('SM_VIDEO_APERTURE] = std::make_unique<CGLShader>', shader)
        self.assertIn('"gl_shader_vert.glsl", "gl_shader_frag_default.glsl"', shader)
        for version in ("1.2", "1.5"):
            vertex = (TREE / "system/shaders/GL" / version / "gl_shader_vert.glsl").read_text()
            self.assertIn("gl_Position.z = m_depth * gl_Position.w", vertex)
