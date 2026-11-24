#include <cassert>
#include <cstdint>
#include <map>
#include <memory>
#include <optional>
#include <string>
#include <vector>
struct CDRMPropertyBlob {
 CDRMPropertyBlob()=default;CDRMPropertyBlob(int,void*,int){}
 bool IsValid() const {return true;}uint64_t Get() const {return 1;}
};
struct CDRMObject {
 std::map<std::string,uint64_t> cache;
 std::map<std::string,std::map<std::string,uint64_t>> enums;
 std::optional<uint64_t> GetPropertyValue(const char* name) const {
  auto it=cache.find(name);if(it==cache.end())return {};return it->second;}
 std::optional<bool> IsPropertyImmutable(const char*) const {return false;}
 std::optional<uint64_t> GetPropertyEnumValue(const char* name,const char* label) const {
  auto p=enums.find(name);if(p==enums.end())return {};auto it=p->second.find(label);
  if(it==p->second.end())return {};return it->second;}
};
struct CDRMConnector:CDRMObject {
 std::string type="HDMI-A";
 std::string GetType() const{return type;}
 bool SupportsProperty(const char* name) const{return cache.contains(name);}
};
inline constexpr int QUIRK_AMD_HDR10_HDMI_AUTO_FORMAT = 4;
struct CDRMUtils {virtual ~CDRMUtils()=default;};
struct CDRMAtomic : CDRMUtils {
 CDRMConnector connector;std::map<std::string,uint64_t> pending;bool addSuccess=true;
 CDRMConnector* GetConnector(){return &connector;}
 int GetFileDescriptor(){return 1;}
 bool amd=false;
 bool HasQuirk(int quirk) const{return amd && quirk==QUIRK_AMD_HDR10_HDMI_AUTO_FORMAT;}
 bool pendingPage=false;bool HasPendingCB1Page() const{return pendingPage;}
 bool AddProperty(CDRMObject*,const char* name,uint64_t value){
  if(!addSuccess)return false;pending[name]=value;return true;}
 void Commit(bool accepted){if(accepted)for(auto [n,v]:pending)connector.cache[n]=v;pending.clear();}
};
struct Blob {void* data=nullptr;int length=0;};
Blob* drmModeGetPropertyBlob(int,uint64_t){return nullptr;}void drmModeFreePropertyBlob(Blob*){}
// NATIVE_DECLARATION
// NATIVE_METHODS
struct CWinSystemGbmGLESContext {
 std::shared_ptr<CDRMUtils> m_DRM=std::make_shared<CDRMAtomic>();
 CDVBridgeState m_dvState,m_cb1ConnectorState;
 bool m_dvStopPending=false;
 bool m_cb1RestoringPreferences=false,m_hdrConversion=false,m_sdrConversion=false,m_dvOrdinaryFrame=false,m_dvEndPending=false;
 bool pendingRestore=false,m_dvOutputSurface=false,pendingSurface=false;
 bool requestedLimited=false,ordinaryLimited=false;int deferred=0,colorSpaceRefreshes=0;
 std::shared_ptr<void> m_nativeDVProperties;
 std::optional<bool> m_cb1LimitedRange,m_cb1OrdinaryLimitedRange;
 std::optional<uint64_t> m_cb1LimitedBroadcastRange,m_hdr10AutoColorFormat;
 bool HasPendingDVBridgeRestore() const {return pendingRestore;}
 bool HasPendingDVOutputSurface() const {return pendingSurface;}
 bool RequestedLimitedColor() const{return requestedLimited;}
 bool OrdinaryShaderLimitedColor(){return ordinaryLimited;}
 std::optional<uint64_t> DefaultMaxBpc() const{return 12;}
 void DeferConnectorPreferences(){++deferred;}
 void ApplyColorspace(){++colorSpaceRefreshes;}
 void SetHDR(std::nullptr_t){assert(false);}
 bool CaptureCB1ConnectorPreferences();bool StageCB1ConnectorPreferences(bool);
 bool StageTransportPreferences();bool ConnectorPreferencesAllowed() const;
 std::optional<bool> TransportLimitedColor() const;
 std::optional<uint64_t> RestoredConnectorProperty(const char*) const;
 void CompleteCB1ConnectorRestore();
};
// NATIVE_CONTROLLER
int main(){
 CDRMAtomic drm;drm.connector.cache={{"Broadcast RGB",2},{"color format",3},{"max bpc",8}};
 drm.connector.enums={{"Broadcast RGB",{{"Full",1},{"Limited 16:235",2}}},
                      {"color format",{{"AUTO",0},{"RGB",1},{"YUV 4:2:2",3}}}};
 CDVBridgeState state;assert(state.CaptureColorPreferences(drm,12));
 assert(state.Before("Broadcast RGB")==2 && state.Before("color format")==3);
 assert(state.Stage(drm,false));
 assert(drm.pending.at("Broadcast RGB")==1 && drm.pending.at("color format")==1 && drm.pending.at("max bpc")==12);
 drm.Commit(false);assert(drm.connector.cache.at("color format")==3 && state.Captured());
 assert(state.Stage(drm,false));drm.Commit(true);
 assert(drm.connector.cache.at("color format")==1 && state.Before("color format")==3);
 assert(state.CaptureColorPreferences(drm,10)); // an active route change retains original before-values
 assert(state.Stage(drm,true));
 assert(drm.pending.at("Broadcast RGB")==2 && drm.pending.at("color format")==3 && drm.pending.at("max bpc")==8);
 drm.Commit(false);assert(state.Captured() && drm.connector.cache.at("color format")==1);
 assert(state.Stage(drm,true));drm.Commit(true);state.Restored();
 assert(!state.Captured() && drm.connector.cache.at("color format")==3);
 CDRMAtomic other;assert(!state.Stage(other,true));
 CDRMAtomic absent;assert(state.CaptureColorPreferences(absent,{}));
 assert(!state.Captured() && absent.pending.empty());
 CDRMAtomic unsupported;unsupported.connector.cache["color format"]=3;
 assert(!state.CaptureColorPreferences(unsupported,{}));assert(!state.Captured());
 CDRMAtomic missingFormat;missingFormat.connector.cache={{"Broadcast RGB",2},{"max bpc",10}};
 missingFormat.connector.enums={{"Broadcast RGB",{{"Full",1}}}};
 assert(state.CaptureColorPreferences(missingFormat,12));assert(state.Stage(missingFormat,false));
 assert(missingFormat.pending.size()==2 && missingFormat.pending.at("max bpc")==12);
 state.Restored();
 CWinSystemGbmGLESContext w;auto output=std::dynamic_pointer_cast<CDRMAtomic>(w.m_DRM);
 output->connector=drm.connector; // original accepted YUV, Limited, 8bpc
 w.requestedLimited=true;w.ordinaryLimited=false;
 assert(w.CaptureCB1ConnectorPreferences() && !w.ConnectorPreferencesAllowed());
 w.requestedLimited=false;w.ordinaryLimited=true;
 assert(w.CaptureCB1ConnectorPreferences());assert(w.TransportLimitedColor()==true);
 assert(w.StageCB1ConnectorPreferences(false));assert(output->pending.at("max bpc")==12);
 w.m_sdrConversion=true;
 assert(w.TransportLimitedColor()==false); // The driver compresses full-range rendered pixels.
 assert(w.StageCB1ConnectorPreferences(false) && output->pending.at("Broadcast RGB")==2);
 assert(w.StageCB1ConnectorPreferences(true) && output->pending.at("Broadcast RGB")==2);
 assert(w.StageCB1ConnectorPreferences(false));
 w.m_sdrConversion=false;
 assert(w.TransportLimitedColor()==true);
 assert(w.StageCB1ConnectorPreferences(false) && output->pending.at("Broadcast RGB")==1);
 assert(w.m_dvState.CaptureColorPreferences(*output,8));assert(w.m_dvState.Stage(*output,false));
 assert(output->pending.at("max bpc")==8);assert(w.StageTransportPreferences());
 assert(output->pending.at("max bpc")==8); // native DV owner wins over baseline 12bpc
 w.m_hdrConversion=true;assert(w.StageTransportPreferences());assert(output->pending.at("max bpc")==12);
 assert(output->pending.at("color format")==1); // Other DRM drivers retain RGB.
 assert(w.StageCB1ConnectorPreferences(true));
 assert(w.TransportLimitedColor()==false && w.RestoredConnectorProperty("color format")==3);
 assert(w.StageTransportPreferences() && w.colorSpaceRefreshes==1);
 output->Commit(false);assert(w.m_cb1ConnectorState.Captured());
 assert(w.StageCB1ConnectorPreferences(true));output->Commit(true);w.CompleteCB1ConnectorRestore();
 assert(!w.m_cb1ConnectorState.Captured() && !w.m_cb1LimitedRange && !w.m_cb1OrdinaryLimitedRange);
 assert(!w.m_cb1LimitedBroadcastRange && !w.m_hdr10AutoColorFormat);
 for (bool limited : {false,true}) {
  for (int device : {0,1,2,3,4,5}) {
   CWinSystemGbmGLESContext hdr;
   auto native=std::dynamic_pointer_cast<CDRMAtomic>(hdr.m_DRM);
   native->amd=device!=1;
   native->connector=drm.connector;
   native->connector.type=device==2 ? "DP" : "HDMI-A";
   if (device!=3) native->connector.cache["DVBRIDGE_HDR10_DEEP_COLOR"]=0;
   if (device==4) native->connector.enums["color format"].erase("AUTO");
   if (device==5) native->connector.cache.erase("Broadcast RGB");
   hdr.requestedLimited=limited;
   assert(hdr.CaptureCB1ConnectorPreferences());
   assert(hdr.m_dvState.CaptureColorPreferences(*native,8));
   assert(hdr.m_dvState.Stage(*native,false) && hdr.StageTransportPreferences());
   assert(native->pending.at("color format")==1);
   native->Commit(true);
   hdr.m_hdrConversion=true;
   assert(hdr.StageTransportPreferences());
   const bool automatic=device==0;
   assert(hdr.TransportLimitedColor()==(limited && !automatic));
   assert(native->pending.at("color format")==uint64_t(automatic ? 0 : 1));
   assert(native->pending.at("max bpc")==12);
   if (device!=5)
     assert(native->pending.at("Broadcast RGB")==uint64_t(automatic && limited ? 2 : 1));
   native->Commit(false);
   assert(native->connector.cache.at("color format")==1 && hdr.m_dvState.Captured());
   assert(hdr.StageTransportPreferences());
   native->Commit(true);
   assert(native->connector.cache.at("color format")==uint64_t(automatic ? 0 : 1));
   hdr.m_sdrConversion=true; // SDR also uses the HDR conversion compositor.
   assert(hdr.StageTransportPreferences() && native->pending.at("color format")==1);
   hdr.m_sdrConversion=false;
   assert(hdr.StageCB1ConnectorPreferences(true));
   assert(native->pending.at("color format")==3);
  }
 }
 for (bool hasRange : {false,true}) {
  CWinSystemGbmGLESContext sdr;
  auto native=std::dynamic_pointer_cast<CDRMAtomic>(sdr.m_DRM);
  native->connector.cache["max bpc"]=8;
  if(hasRange) {
   native->connector.cache["Broadcast RGB"]=0;
   native->connector.enums["Broadcast RGB"]={{"Full",1}};
  }
  sdr.requestedLimited=true;
  sdr.m_sdrConversion=true;
  assert(sdr.CaptureCB1ConnectorPreferences() && sdr.StageCB1ConnectorPreferences(false));
  assert(sdr.TransportLimitedColor()==!hasRange);
  assert(native->pending.contains("Broadcast RGB")==hasRange);
  if(hasRange) assert(native->pending.at("Broadcast RGB")==1);
 }
 w.m_dvState.Restored();w.m_hdrConversion=false;assert(w.ConnectorPreferencesAllowed());
 for(int flag=0;flag<7;++flag){
  w.pendingRestore=flag==0;w.m_dvOutputSurface=flag==1;w.pendingSurface=flag==2;
  w.m_dvOrdinaryFrame=flag==3;w.m_dvEndPending=flag==4;output->pendingPage=flag==5;
  w.m_nativeDVProperties=flag==6?std::make_shared<int>(1):nullptr;
  assert(!w.ConnectorPreferencesAllowed());
 }
}
