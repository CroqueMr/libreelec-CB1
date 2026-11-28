"""Exercise native SDR admission reuse and exact live-switch invalidation."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_native_video_source import TREE, body


class NativeSDRFastPath(unittest.TestCase):
    def test_native_playback_prepares_only_changed_admission(self):
        path = TREE / "xbmc/windowing/gbm"
        signatures = [f"bool CWinSystemGbm{api}Context::PrepareRendererFrame(" for api in ("GL", "GLES")]
        sources = [(path / f"WinSystemGbm{api}Context.cpp").read_text() for api in ("GL", "GLES")]
        # The old renderer always executed the complete preparation and selection.
        old = "{ if (!PrepareDVOutputFrame(picture)) return false; requested=DVBridgeRequested(&picture); return true; }"
        methods = [body(s, signature) if signature in s else old for s, signature in zip(sources, signatures)]
        self.assertEqual(*methods)
        code = r"""
#include <cassert>
#include <cstdint>
#include <memory>
#include <mutex>
#include <optional>
#include <tuple>
namespace DVBRIDGE {
bool native=true;
bool NativeSDRPlayback(){return native;}
struct SourceBinding {
 uint64_t stream=1,picture=1,revision=1;
 bool Valid()const{return stream&&picture&&revision;}
 bool operator==(const SourceBinding&)const=default;
};
enum class OutputRoute{Vanilla,NativeDV};
}
struct VideoPicture {bool sdr=true;DVBRIDGE::SourceBinding doviSourceBinding;};
namespace DVBRIDGE {bool IsSDRExpansionSource(const VideoPicture&p){return p.sdr;}}
struct Context{bool GL()const{return true;}};
struct Window {
 std::shared_ptr<const VideoPicture> m_deferredOrdinaryPicture;
 bool m_dvStopPending=false;
 bool m_dvOrdinaryFrame=false,m_dvEndPending=false,m_dvRecoveryPending=false,
      m_dvRejectedSurface=false,m_dvRollbackFailed=false,m_dvActivating=false,
      m_dvOutputRetiring=false,m_dvSuperseded=false,m_dvShutdownFence=false;
 bool restore=false,pending=false,prepareOK=true,m_dvBridge=false,switchDuringPrepare=false;
 Context* m_dvContext=nullptr;
 struct {DVBRIDGE::OutputRoute route=DVBRIDGE::OutputRoute::Vanilla;}m_dvSelection;
 struct {uint64_t generation=1;}m_dvCapabilities;
 DVBRIDGE::SourceBinding m_dvImportBinding;
 uint64_t m_dvImportGeneration=1;
 bool m_dvImportUsable=true;
 std::mutex m_dvCapabilityMutex;
 uint64_t m_nativeSDRCapabilityRevision=0;
 struct{uint64_t connectorId=1,edidGeneration=1;}m_dvLldvStatus;
 using NativeSDRAdmission=std::tuple<uint64_t,uint64_t,uint64_t,uint64_t,uint64_t,uint64_t,bool>;
 std::optional<NativeSDRAdmission> m_nativeSDRAdmission;
 unsigned prepares=0,selects=0;
 bool HasPendingDVBridgeRestore()const{return restore;}
 bool HasPendingDVOutputSurface()const{return pending;}
 bool PrepareDVOutputFrame(const VideoPicture&){++prepares;
   if(switchDuringPrepare){DVBRIDGE::native=false;m_dvSelection.route=DVBRIDGE::OutputRoute::NativeDV;}
   return prepareOK;}
 bool DVBridgeRequested(const VideoPicture*){++selects;return !DVBRIDGE::native;}
 bool PrepareRendererFrame(const VideoPicture& picture, bool& requested) BODY
};
int main(){
 Window w;VideoPicture p;bool requested=true;
 for(unsigned n=1;n<=100;n++){
  p.doviSourceBinding.picture=n;w.m_dvImportBinding=p.doviSourceBinding;
  assert(w.PrepareRendererFrame(p,requested)&&!requested);
 }
 assert(w.prepares==1 && w.selects==0);
 auto step=[&](){w.m_dvImportBinding=p.doviSourceBinding;assert(w.PrepareRendererFrame(p,requested));};
 // Seek, new source, changed receiver, and unusable import all re-admit once.
 ++p.doviSourceBinding.revision;step();assert(w.prepares==2);
 ++p.doviSourceBinding.stream;step();assert(w.prepares==3);
 ++w.m_dvCapabilities.generation;++w.m_dvImportGeneration;step();assert(w.prepares==4);
 w.m_dvImportUsable=false;step();assert(w.prepares==5);
 step();assert(w.prepares==5);
 // Current frame still has its original binding even if playback is paused.
 DVBRIDGE::native=false;step();assert(requested && w.prepares==6);
 DVBRIDGE::native=true;w.restore=true;w.prepareOK=false;
 assert(!w.PrepareRendererFrame(p,requested));assert(w.prepares==7);
   auto retained=std::make_shared<VideoPicture>(p);
   w.m_deferredOrdinaryPicture=retained;
   w.m_dvOrdinaryFrame=true;
   assert(w.PrepareRendererFrame(*retained,requested) && !requested && w.prepares==7);
   w.m_deferredOrdinaryPicture.reset();w.m_dvOrdinaryFrame=false;

 w.restore=false;w.prepareOK=true;Context idle;w.m_dvContext=&idle;w.m_dvBridge=true;step();assert(!requested && w.prepares==8);
 step();assert(w.prepares==8);
 w.pending=true;step();assert(w.prepares==9);
 w.pending=false;step();assert(w.prepares==10);
 w.m_dvImportBinding={0,0,0};assert(w.PrepareRendererFrame(p,requested));assert(w.prepares==11);
 // Unrelated HDR always retains the pre-existing full admission.
 p.sdr=false;step();assert(w.prepares==12);
 p.sdr=true;step();assert(w.prepares==13);
 ++w.m_nativeSDRCapabilityRevision;step();assert(w.prepares==14);
 ++w.m_dvLldvStatus.edidGeneration;step();assert(w.prepares==15);
 ++w.m_dvLldvStatus.connectorId;step();assert(w.prepares==16);
 step();assert(w.prepares==16);
 Window race;VideoPicture same;race.m_dvImportBinding=same.doviSourceBinding;
 race.switchDuringPrepare=true;
 assert(race.PrepareRendererFrame(same,requested)&&requested&&!race.m_nativeSDRAdmission);

}
""".replace("BODY", methods[0])
        with tempfile.TemporaryDirectory() as root:
            exe=Path(root)/"native"
            build=subprocess.run(["c++","-std=c++20","-x","c++","-","-o",str(exe)],input=code,text=True,capture_output=True)
            self.assertEqual(build.returncode,0,build.stderr)
            result=subprocess.run([str(exe)],text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)

    def test_sdr_buffer_reuse_does_not_mutate_a_live_lease(self):
        # Compile the same acquire/retire implementation used by GL and GLES.
        paths=[TREE / f"xbmc/cores/VideoPlayer/VideoRenderers/LinuxRenderer{api}.cpp" for api in ("GL","GLES")]
        acquire=[];release=[]
        for p in paths:
            s=p.read_text()
            a=body(s,f"void C{p.stem}::AddVideoPicture(")
            start=a.index("  if (picture.doviSourceBinding.Valid()")
            acquire.append(a[start:a.index("#endif",start)])
            r=body(s,f"void C{p.stem}::ReleaseBuffer(")
            start=r.index("  buf.doviEnhancementBinding = {};")+len("  buf.doviEnhancementBinding = {};")
            release.append(r[start:r.index("#endif",start)])
        self.assertEqual(*acquire)
        self.assertEqual(*release)
        code=r"""
#include <memory>
#include <cassert>
struct Binding{bool valid=true;bool Valid()const{return valid;}};
struct VideoPicture{
 bool sdr=true;unsigned value=0;Binding doviSourceBinding;
 struct{bool Data()const{return false;}}doviMetadata;
 void CopyRef(const VideoPicture& p){*this=p;}
 void Reset(){value=0;}
};
namespace DVBRIDGE{bool IsSDRExpansionSource(const VideoPicture&p){return p.sdr;}}
struct Slot{std::shared_ptr<VideoPicture> doviSourcePicture,recycledSDRPicture;}buf;
void add(const VideoPicture& picture){ ACQUIRE }
void retire(){ RELEASE }
int main(){
 VideoPicture p;p.value=1;add(p);auto ptr=buf.doviSourcePicture.get();std::weak_ptr<VideoPicture> lifetime=buf.doviSourcePicture;
 retire();assert(!lifetime.expired());p.value=2;add(p);
 assert(buf.doviSourcePicture.get()==ptr && buf.doviSourcePicture->value==2);
 auto lease=buf.doviSourcePicture;retire();p.value=3;add(p);
 assert(lease->value==2 && lease!=buf.doviSourcePicture);
 retire();p.sdr=false;p.value=4;add(p);
 assert(buf.doviSourcePicture->value==4 && !buf.recycledSDRPicture);
}
""".replace("ACQUIRE",acquire[0]).replace("RELEASE",release[0])
        with tempfile.TemporaryDirectory() as root:
            exe=Path(root)/"lease"
            build=subprocess.run(["c++","-std=c++20","-x","c++","-","-o",str(exe)],input=code,text=True,capture_output=True)
            self.assertEqual(build.returncode,0,build.stderr)
            result=subprocess.run([str(exe)],text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
