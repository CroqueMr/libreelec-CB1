"""Replay a Blu-ray still encountered while FFmpeg is probing the next stream."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_native_video_source import TREE, body


class BlurayDemuxRetry(unittest.TestCase):
    def test_still_defers_probe_until_the_navigator_has_an_open_event(self):
        player = (TREE / 'xbmc/cores/VideoPlayer/VideoPlayer.cpp').read_text()
        opening = body(player, 'bool CVideoPlayer::OpenDemuxStream()')
        probe = opening.split('#if defined(HAVE_LIBBLURAY)', 1)[0]
        program = r'''
#include <cassert>
#include <memory>
struct CDVDInputStream {
  enum ENextStream { NEXTSTREAM_NONE, NEXTSTREAM_OPEN, NEXTSTREAM_RETRY };
  ENextStream next=NEXTSTREAM_RETRY;
  bool readable=false;
  bool IsStreamType(int) const { return false; }
  ENextStream NextStream() { return next; }
};
struct CDVDFactoryDemuxer {
  static inline int probes=0;
  static int* CreateDemuxer(const std::shared_ptr<CDVDInputStream>& input) {
    ++probes;
    return input->readable ? new int(0) : nullptr;
  }
};
constexpr int DVDSTREAM_TYPE_PVRMANAGER=5, LOGINFO=0, LOGDEBUG=1, LOGERROR=2;
struct CLog { template<class... T> static void Log(T...) {} };
struct CVideoPlayer {
  bool m_blurayDemuxDeferred=false, m_bStop=false, bdjStill=true;
  std::unique_ptr<int> m_pDemuxer;

  std::shared_ptr<CDVDInputStream> m_pInputStream=std::make_shared<CDVDInputStream>();
  bool WaitingForBlurayStill() const { return bdjStill; }
  void CloseDemuxer() { m_pDemuxer.reset(); }
  bool WaitForBlurayPlaylist() { return false; }
  bool OpenDemuxStream() PREFIX
    return true;
  }
};
int main() {
  CVideoPlayer player;
  assert(!player.OpenDemuxStream());
  assert(player.m_blurayDemuxDeferred && CDVDFactoryDemuxer::probes==1 &&
         "Blu-ray RETRY must defer the demuxer instead of exhausting probes");
  player.m_pInputStream->next=CDVDInputStream::NEXTSTREAM_OPEN;
  player.m_pInputStream->readable=true;
  assert(player.OpenDemuxStream() && player.m_pDemuxer && !player.m_blurayDemuxDeferred);
  assert(CDVDFactoryDemuxer::probes==2);

  CVideoPlayer terminal;
  terminal.m_pInputStream->next=CDVDInputStream::NEXTSTREAM_NONE;
  assert(!terminal.OpenDemuxStream() && !terminal.m_blurayDemuxDeferred);
  assert(CDVDFactoryDemuxer::probes==3);

  CVideoPlayer waitingForBdjEnd;
  waitingForBdjEnd.bdjStill=false;
  assert(!waitingForBdjEnd.OpenDemuxStream() && !waitingForBdjEnd.m_blurayDemuxDeferred);
  assert(CDVDFactoryDemuxer::probes==13);
}
'''.replace('PREFIX', probe)
        self.run_cpp(program)

    def test_wait_services_the_navigator_and_keeps_the_original_still_deadline(self):
        player = (TREE / 'xbmc/cores/VideoPlayer/VideoPlayer.cpp').read_text()
        process = body(player, 'void CVideoPlayer::Process()')
        pending = process.split('const auto next = m_pInputStream->NextStream();', 1)[1]
        wait = pending.split('if (next == CDVDInputStream::NEXTSTREAM_NONE)', 1)[1]
        wait = wait[wait.index('if (next == CDVDInputStream::NEXTSTREAM_RETRY'):].split(
            'if (m_pInputStream->IsEOF())', 1)[0]
        expiry = body(player, 'bool CVideoPlayer::SkipExpiredMenuStill()')
        program = r'''
#include <cassert>
#include <chrono>
#include <memory>
using namespace std::chrono_literals;
constexpr int DVDSTATE_STILL=1, DVDSTATE_NORMAL=0, DVD_PLAYSPEED_PAUSE=0;
struct CDVDInputStream {
  enum ENextStream { NEXTSTREAM_NONE, NEXTSTREAM_OPEN, NEXTSTREAM_RETRY };
  struct IMenus { virtual void SkipStill()=0; virtual ~IMenus()=default; };
  virtual ~CDVDInputStream()=default;
};
struct Input : CDVDInputStream, CDVDInputStream::IMenus {
  int skips=0;
  void SkipStill() override { ++skips; }
};
struct CThread {
  static inline int sleeps=0;
  static void Sleep(std::chrono::milliseconds duration) { assert(duration==50ms); ++sleeps; }
};
struct CVideoPlayer {
  std::shared_ptr<CDVDInputStream> m_pInputStream=std::make_shared<Input>();
  struct {
    int state=DVDSTATE_STILL;
    std::chrono::milliseconds iDVDStillTime=0ms;
    std::chrono::steady_clock::time_point iDVDStillStartTime=std::chrono::steady_clock::now();
  } m_dvd;
  int m_playSpeed=1;
  int eventPasses=0;
  bool bdjStill=true;
  bool WaitingForBlurayStill() const { return bdjStill; }
  bool WaitForBlurayPlaylist() { ++eventPasses; return false; }
  bool SkipExpiredMenuStill() EXPIRY
  bool probe(CDVDInputStream::ENextStream next) {
    for(int pass=0;pass<1;pass++) {
      WAIT
      return true;
    }
    return false;
  }
};
int main() {
  using CDVDInputStream::NEXTSTREAM_OPEN;
  using CDVDInputStream::NEXTSTREAM_RETRY;
  CVideoPlayer player;
  const auto start=player.m_dvd.iDVDStillStartTime;
  for(int i=0;i<4;i++) assert(!player.probe(NEXTSTREAM_RETRY));
  assert(player.eventPasses==4 && CThread::sleeps==4);
  assert(player.m_dvd.state==DVDSTATE_STILL && player.m_dvd.iDVDStillStartTime==start);
  assert(player.probe(NEXTSTREAM_OPEN));

  auto& input=static_cast<Input&>(*player.m_pInputStream);
  player.m_dvd.iDVDStillTime=1000ms;
  player.m_dvd.iDVDStillStartTime=std::chrono::steady_clock::now()-2000ms;
  player.m_playSpeed=DVD_PLAYSPEED_PAUSE;
  assert(!player.probe(NEXTSTREAM_RETRY) && input.skips==0);
  player.m_playSpeed=1;
  assert(!player.probe(NEXTSTREAM_RETRY) && input.skips==1);
  assert(player.m_dvd.state==DVDSTATE_NORMAL && player.m_dvd.iDVDStillTime==0ms);
  assert(player.probe(NEXTSTREAM_OPEN));
}
'''.replace('EXPIRY', expiry).replace('WAIT', wait)
        self.run_cpp(program)

    def run_cpp(self, program):
        with tempfile.TemporaryDirectory() as temporary:
            binary = Path(temporary) / 'demux-retry'
            subprocess.run(['c++', '-std=c++20', '-Wall', '-Wextra', '-Werror', '-x', 'c++',
                            '-', '-o', str(binary)], input=program, text=True, check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    unittest.main()
