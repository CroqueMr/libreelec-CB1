"""Exercise transport restoration on the current and replacement GBM drawables."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from test_native_video_source import TREE, body


class NvidiaBufferRestore(unittest.TestCase):
    def test_restore_preserves_target_signal_and_buffer_ownership(self):
        base = TREE / 'xbmc/windowing/gbm'
        window = (base / 'WinSystemGbm.cpp').read_text()
        header = (base / 'WinSystemGbm.h').read_text()
        context = (base / 'WinSystemGbmGLESContext.cpp').read_text()
        surface = (base / 'GBMUtils.cpp').read_text()
        present = body(context, 'void CWinSystemGbmGLESContext::PresentFrame(')
        ordinary = present.split('\n  if (m_dvOrdinaryFrame)\n', 1)[1]
        ordinary = ordinary[:ordinary.index('    if (!submitted)')]
        ordinary = ordinary[ordinary.index('{') + 1:].replace('return;', 'return false;') + '\nreturn submitted;'
        hdr = present.split('  if (m_hdrConversion)\n', 1)[1]
        hdr = hdr[hdr.index('        auto drm ='):hdr.index('      }\n      else if (asynchronous')]
        end = body(context, 'bool CWinSystemGbmGLESContext::EndDVBridge(')
        captured = body(end, 'if (m_dvState.Captured())')
        immediate = captured[captured.index('    AnnounceCB1Mode(false);'):captured.index('    if (!restored)')]
        signature = re.search(r'bool FlipDVBridgePage\([^;]+;', header).group()
        program = r'''
#include <cassert>
#include <cstdint>
#include <memory>
#include <queue>
#include <string_view>
#include <optional>
#include <vector>
struct gbm_bo {unsigned format=1;};
constexpr unsigned DRM_FORMAT_XRGB8888=1,DRM_FORMAT_ARGB8888=2;
constexpr unsigned DRM_MODE_FLAG_INTERLACE=1,DRM_MODE_FLAG_DBLSCAN=2;
enum {DVBRIDGE_GAMUT_BT709,DVBRIDGE_GAMUT_BT2020};
enum {AVCOL_TRC_BT709,AVCOL_PRI_BT709,AVCOL_PRI_BT2020,AVCOL_SPC_BT709,AVCOL_SPC_BT2020_NCL};
struct VideoPicture {int color_transfer{},color_primaries{},color_space{},colorBits{};};
unsigned gbm_bo_get_format(gbm_bo* bo){return bo->format;}
unsigned gbm_bo_get_width(gbm_bo*){return 3840;}
unsigned gbm_bo_get_height(gbm_bo*){return 2160;}
struct CResolutionUtils {static bool IsCB1RefreshRate(double){return true;}};
struct DRM {virtual ~DRM()=default;};
inline constexpr int QUIRK_AMD_HDR10_HDMI_AUTO_FORMAT = 4;
struct CDRMAtomic:DRM {
 bool HasQuirk(int)const{return false;}
 struct Connector {std::string_view GetType()const{return "HDMI-A";}
  bool strict=false;bool SupportsProperty(const char* name){return strict && std::string_view(name)=="DVBRIDGE_HDR10_DEEP_COLOR";}
  std::optional<int> GetPropertyEnumValue(const char*,const char*)const{return {};}}connector;
 struct Mode {unsigned hdisplay=3840,vdisplay=2160,flags=0,htotal=4400,vtotal=2250,clock=594000;}mode;
 bool stageOK=true,commitOK=true,active=false;unsigned accepted=0,missing=0;
 int stagedHDR=-1,stagedGuard=-1;
 unsigned rejectAttempt=0;
 std::vector<int> attemptedHDR,attemptedGuard;
 gbm_bo* acceptedBuffer=nullptr;
 auto* GetConnector(){return &connector;} auto* GetSelectedMode(){return &mode;}
 bool AddProperty(Connector*,const char* name,int value){if(std::string_view(name)=="DVBRIDGE_HDR10_DEEP_COLOR")stagedGuard=value;return true;}
 bool IsActive(){return active;} bool IsSelectedModeCommitted(){return true;}
 void SetActive(bool value){active=value;}
 bool HasPendingCB1Page(){return false;}
 bool FlipPageTransactional(gbm_bo* bo,bool,bool=false){
   if(!bo){++missing;return false;}
   attemptedHDR.push_back(stagedHDR);attemptedGuard.push_back(stagedGuard);stagedGuard=-1;
   stagedHDR=-1;
   if(!commitOK || attemptedHDR.size()==rejectAttempt)return false;
   ++accepted;acceptedBuffer=bo;return true;
 }
 void StageHDR10Plus(int,int){}
 void SetCB1PresentationPts(double){}
 bool HDR10PlusActive(){return false;}
};
struct CDVBridgeState {
 enum class Backend{KERNEL,NVIDIA};Backend backend=Backend::NVIDIA;bool captured=true;
 bool Captured(){return captured;}Backend CapturedBackend(){return backend;}
 int capturedHDR=461;
 bool Stage(CDRMAtomic& drm,bool restore){if(restore){drm.stagedHDR=capturedHDR;if(drm.connector.strict)drm.stagedGuard=0;}return drm.stageOK;}
 void Restored(){captured=false;}
};
struct Surface {
 struct CGBMSurfaceBuffer {
   gbm_bo buffer;bool available;explicit CGBMSurfaceBuffer(bool available):available(available){}
   gbm_bo* external{};std::shared_ptr<void> lease;
   CGBMSurfaceBuffer(gbm_bo* bo,std::shared_ptr<void> owner)
     :available(true),external(bo),lease(std::move(owner)){}
   gbm_bo* Get(){return external?external:available?&buffer:nullptr;}
 };
 bool m_surface=true;
 std::unique_ptr<CGBMSurfaceBuffer> m_pendingBuffer,m_scanoutBuffer;
 std::queue<std::unique_ptr<CGBMSurfaceBuffer>> m_buffers;
 Surface& GetDevice(){return *this;}Surface& GetSurface(){return *this;}
 gbm_bo* LockTransactionalBuffer() @LOCK@
 gbm_bo* AdoptTransactionalBuffer(gbm_bo* buffer,std::shared_ptr<void> lease) @ADOPT@
 void CompleteTransactionalBuffer(bool presented) @COMPLETE@
 void EndTransactionalMode() @END@
};
namespace DVBRIDGE {struct PlaybackNotification{static void OrdinaryOutputAccepted(bool){}};}
struct Window {
 std::shared_ptr<DRM> m_DRM=std::make_shared<CDRMAtomic>();
 std::shared_ptr<Surface> m_GBM=std::make_shared<Surface>();
 CDVBridgeState m_dvState;bool m_dvStopPending=false,m_sdrConversion=false;
 struct {struct {struct {int gamut=DVBRIDGE_GAMUT_BT709;}sdr;}policy;}m_dvSelection;
 bool SDRBT2020DeepColorSupported()const{return false;}
 std::optional<uint64_t> SDRBT2020MaxBpc()const{assert(false && "legacy transport must not request a wide-SDR floor");return {};}
 struct {
   bool captured=false;
   unsigned staged=0;
   bool Captured(){return captured;}
   bool Stage(CDRMAtomic&,bool,std::optional<uint64_t>,std::optional<uint64_t> colorFormat,
              std::optional<uint64_t> wideSDRMaxBpc){
     ++staged;
     assert(!wideSDRMaxBpc && "legacy transport must not assert the AMD guard");
     return !colorFormat;}
 } m_cb1ConnectorState;
 bool m_cb1RestoringPreferences=false,m_hdrConversion=false;
 std::optional<uint64_t> m_cb1LimitedBroadcastRange,m_hdr10AutoColorFormat;
 void ApplyColorspace(){}
 std::optional<int> m_queuedColorspace;
 int GetOutputBitDepth(){return 8;}
 void SetHDR(const VideoPicture* picture){
   assert(!picture);
   std::static_pointer_cast<CDRMAtomic>(m_DRM)->stagedHDR=0;
 }
 void SetColorimetry(const VideoPicture* picture){assert(!picture);}
 double m_preparedRenderPts{};
 unsigned m_preparedSource{7},m_cb1PageSource{},m_cb1DisplayedSource{};
 void TrackCB1VideoPage(bool pending) @TRACK@
 std::optional<uint64_t>m_hdrDeepColorPrevious;
 enum class PascalHDRMode {None,Conversion,Native};
 PascalHDRMode m_pascalHDRMode=PascalHDRMode::None;
 std::shared_ptr<gbm_bo> BlitNativePascalHDRFrame(){assert(m_pascalHDRMode!=PascalHDRMode::Native);return {};}
 bool StageNativePascalHDR10(){assert(false);return false;}
 void StageNativeHDR10Plus(){assert(false);}
 struct AlternateScanout {unsigned accepted{};void Presented(){++accepted;}};
 AlternateScanout scanout;AlternateScanout* m_pascalHDRScanout=&scanout;
 struct EGL {bool TrySwapBuffers(){return true;}} m_eglContext;
 bool PrepareOrdinaryDVOutput(void*){return true;}
 bool CompleteDVBridgePage(){return true;}bool SupportsDVOutputMode(){return true;}
 bool StageTransportPreferences() @TRANSPORT@
 bool StageCB1ConnectorPreferences(bool restore) @PREFERENCES@
 bool RequeueOutputProperties(){return true;}bool FloatOutputUsable(){return true;}
 void AnnounceCB1Mode(bool){}void CompleteCB1Mode(bool,bool){}
 @SIGNATURE@
 bool SameDrawableRestore(){@IMMEDIATE@ return restored;}
 bool Ordinary(bool rendered){@ORDINARY@}
 bool HDR(std::shared_ptr<gbm_bo> carrier={}){bool presented=false,asynchronous=false;
   constexpr bool signalChange=false;
   constexpr int gamut=DVBRIDGE_GAMUT_BT709;
   std::optional<int> m_sdrSignal;
   [[maybe_unused]] bool signalRejected=false;
   struct {int hdr10plus=0,informationGeneration=1;bool hdr10plusAccepted=false;}submitted;
   @HDR@
   return presented;
 }
};
@FLIP@
int main(){
 {
   Window legacy;
   legacy.m_cb1ConnectorState.captured=true;
   legacy.m_sdrConversion=true;
   legacy.m_dvSelection.policy.sdr.gamut=DVBRIDGE_GAMUT_BT2020;
   assert(legacy.StageCB1ConnectorPreferences(false));
   assert(legacy.m_cb1ConnectorState.staged==1);
   assert(legacy.StageCB1ConnectorPreferences(true));
   assert(legacy.m_cb1ConnectorState.staged==2);
 }
 // A desktop resize can restore the transport on the current drawable while stop is pending.
 for(bool stopping:{false,true}){
   for(bool nvidia:{false,true}){
     Window w;
     w.m_dvStopPending=stopping;
     w.m_dvState.backend=nvidia?CDVBridgeState::Backend::NVIDIA:CDVBridgeState::Backend::KERNEL;
     auto drm=std::static_pointer_cast<CDRMAtomic>(w.m_DRM);
     drm->active=true;
     // Reject the second leg of an NVIDIA restart or the sole kernel commit.
     drm->rejectAttempt=nvidia?2:1;
     assert(!w.SameDrawableRestore() && w.m_dvState.Captured());
     assert(w.SameDrawableRestore() && !w.m_dvState.Captured());
     assert(drm->attemptedHDR.size()==(nvidia?4:2));
     for(int metadata:drm->attemptedHDR)
       assert(metadata==(stopping?0:w.m_dvState.capturedHDR));
   }
 }
 for(bool hdr:{false,true})for(bool nvidia:{true,false})for(bool active:{false,true})
 for(bool alternate:{false,true}){
   if(alternate&&!hdr)continue;
   auto carrier=alternate?std::make_shared<gbm_bo>():nullptr;
   Window window;auto drm=std::dynamic_pointer_cast<CDRMAtomic>(window.m_DRM);
   window.m_dvState.backend=nvidia?CDVBridgeState::Backend::NVIDIA:CDVBridgeState::Backend::KERNEL;
   drm->active=active;drm->connector.strict=true;
   bool result=hdr?window.HDR(carrier):window.Ordinary(true);
   assert(result && "NVIDIA restoration must not acquire the same GBM buffer twice");
   assert(drm->missing==0 && drm->acceptedBuffer);
   assert(drm->accepted==(nvidia&&active?2u:1u));
   if(hdr) for(int guard:drm->attemptedGuard) assert(guard==1 && "every converted HDR destination commit must retain the strict guard");
   assert(!window.m_GBM->m_pendingBuffer);
   auto& surface=*window.m_GBM;
   assert(drm->acceptedBuffer==(nvidia?surface.m_buffers.back()->Get():surface.m_scanoutBuffer->Get()));
   assert(window.scanout.accepted==(alternate?1u:0u));
   assert(window.m_cb1DisplayedSource==(hdr?window.m_preparedSource:0));
   if(carrier) assert(drm->acceptedBuffer==carrier.get());
   assert(nvidia ? !window.m_dvState.captured : window.m_dvState.captured);
   Window failed;auto fd=std::dynamic_pointer_cast<CDRMAtomic>(failed.m_DRM);
   fd->commitOK=false;
   assert(!(hdr?failed.HDR(carrier):failed.Ordinary(true)) && failed.m_dvState.captured);
   assert(failed.scanout.accepted==0);
   assert(failed.m_cb1DisplayedSource==0 && failed.m_cb1PageSource==0);
   assert(!failed.m_GBM->m_pendingBuffer);
   fd->commitOK=true;
   assert(hdr?failed.HDR(carrier):failed.Ordinary(true));
   if(hdr&&nvidia&&active){
     Window retry;auto rd=std::static_pointer_cast<CDRMAtomic>(retry.m_DRM);
     rd->active=true;rd->connector.strict=true;rd->rejectAttempt=1;
     assert(retry.HDR(carrier));
     assert(rd->attemptedGuard.size()==2);
     for(int guard:rd->attemptedGuard)assert(guard==1);
   }
   Window absent;absent.m_GBM->m_surface=false;
   assert(!(hdr?absent.HDR():absent.Ordinary(true)) && absent.m_dvState.captured);
 }
}
'''
        for marker, value in {
            'LOCK': body(surface, 'gbm_bo* CGBMUtils::CGBMDevice::CGBMSurface::LockTransactionalBuffer('),
            'ADOPT': body(surface, 'gbm_bo* CGBMUtils::CGBMDevice::CGBMSurface::AdoptTransactionalBuffer('),
            'COMPLETE': body(surface, 'void CGBMUtils::CGBMDevice::CGBMSurface::CompleteTransactionalBuffer('),
            'END': body(surface, 'void CGBMUtils::CGBMDevice::CGBMSurface::EndTransactionalMode('),
            'SIGNATURE': signature, 'ORDINARY': ordinary, 'HDR': hdr,
            'IMMEDIATE': immediate,
            'TRACK': body(context, 'void CWinSystemGbmGLESContext::TrackCB1VideoPage('),
            'TRANSPORT': body(context, 'bool CWinSystemGbmGLESContext::StageTransportPreferences('),
            'PREFERENCES': body(context, 'bool CWinSystemGbmGLESContext::StageCB1ConnectorPreferences('),
            'FLIP': 'bool Window::FlipDVBridgePage' +
                window.split('bool CWinSystemGbm::FlipDVBridgePage', 1)[1].split('{', 1)[0] +
                body(window, 'bool CWinSystemGbm::FlipDVBridgePage('),
        }.items():
            program = program.replace('@' + marker + '@', value)
        with tempfile.TemporaryDirectory(prefix='nvidia-restore-') as temporary:
            code, binary = Path(temporary)/'check.cpp', Path(temporary)/'check'
            code.write_text(program)
            build = subprocess.run(['c++', '-std=c++20', '-fsanitize=address,undefined',
                                    str(code), '-o', str(binary)], capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
