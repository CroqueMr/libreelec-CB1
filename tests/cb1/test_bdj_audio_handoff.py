"""BD-J replacement keeps only a viable demuxer and a drained PCM stream."""
import unittest

from test_ai_reentry import execute
from test_native_video_source import TREE, body

PLAYER = TREE / "xbmc/cores/VideoPlayer"


class BdjAudioHandoff(unittest.TestCase):
    def test_abandoned_demuxer_never_opens_workers(self):
        loop = body((PLAYER / "VideoPlayer.cpp").read_text(), "void CVideoPlayer::Process()")
        probe = loop[loop.index("if (!m_pDemuxer)"):loop.index("    HandlePlaySpeed();")]
        self.assertLess(probe.index("OpenDemuxStream()"), probe.index("PollBdjEvents()"))
        self.assertLess(probe.index("PollBdjEvents()"), probe.rindex("TakeBdjPlaylistJump()"))
        self.assertLess(probe.index("CloseDemuxer()"), probe.index("OpenDefaultStreams()"))

    def test_retained_pcm_is_drained_and_paused_in_worker(self):
        loop = body((PLAYER / "VideoPlayer.cpp").read_text(), "void CVideoPlayer::Process()")
        boundary = loop[loop.index("if(next == CDVDInputStream::NEXTSTREAM_OPEN)"):
                        loop.index("if(next == CDVDInputStream::NEXTSTREAM_RETRY)")]
        self.assertIn("m_bdjDraining", boundary)
        self.assertIn("!m_VideoPlayerAudio->IsPassthrough()", boundary)
        self.assertIn("CDVDMsg::GENERAL_EOF", boundary)
        worker = body((PLAYER / "VideoPlayerAudio.cpp").read_text(), "void CVideoPlayerAudio::Process()")
        drain = body(worker, "pMsg->IsType(CDVDMsg::GENERAL_EOF)")
        self.assertLess(drain.index("m_audioSink.Drain()"), drain.index("m_audioSink.Pause()"))
        self.assertLess(drain.index("m_audioSink.GetDelay()"), drain.index("CThread::Sleep(tail)"))
        self.assertLess(drain.index("CThread::Sleep(tail)"), drain.index("m_audioSink.Pause()"))
        self.assertNotIn("m_audioSink.Destroy", drain)

    def test_seek_and_close_release_unselected_audio(self):
        source = (PLAYER / "VideoPlayer.cpp").read_text()
        close = body(source, "bool CVideoPlayer::CloseStream(")
        flush = body(source, "void CVideoPlayer::FlushBuffers(")
        opened = body(source, "bool CVideoPlayer::OpenAudioStream(")
        self.assertIn("m_bdjAudioHandoff", close)
        self.assertIn("CloseStream(m_CurrentAudio, false)", flush)
        self.assertIn("m_bdjAudioHandoff = false", opened)

    def test_reports_the_incoming_decoder_state_after_a_retained_pcm_handoff(self):
        source = (PLAYER / "VideoPlayer.cpp").read_text()
        opened = body(source, "bool CVideoPlayer::OpenAudioStream(")
        execute(r'''
#include <algorithm>
#include <cassert>
#include <memory>
#include <optional>
#include <vector>

struct CDVDMsg
{
  enum Type { GENERAL_EOF, GENERAL_STREAMCHANGE, GENERAL_PAUSE, GENERAL_RESET, PLAYER_REQUEST_STATE };
  Type type;
};
struct CDVDMsgBool : CDVDMsg
{
  CDVDMsgBool(Type type, bool) : CDVDMsg{type} {}
};
struct CDVDStreamInfo
{
  int codec = 0;
  bool operator==(const CDVDStreamInfo&) const = default;
};
struct IDVDStreamPlayer
{
  enum State { SYNC_STARTING, SYNC_INSYNC };
  struct Message { CDVDMsg::Type type; int priority; };
  std::vector<Message> messages;
  void SendMessage(std::shared_ptr<CDVDMsg> message, int priority)
  {
    messages.push_back({message->type, priority});
  }
  bool OpenStream(CDVDStreamInfo&)
  {
    messages.push_back({CDVDMsg::GENERAL_STREAMCHANGE, 0});
    return true;
  }
};
struct IDVDStreamPlayerAudio : IDVDStreamPlayer
{
  void SetSpeed(int) {}
};
struct Player
{
  struct Audio
  {
    int id = -1, player = 0, packets = 0;
    CDVDStreamInfo hint;
    IDVDStreamPlayer::State syncState = IDVDStreamPlayer::SYNC_INSYNC;
  } m_CurrentAudio;
  IDVDStreamPlayerAudio worker;
  std::optional<int> m_syncStartPtsWait;
  bool m_bdjAudioHandoff = true, m_displayLost = false, m_HasAudio = false;
  int m_streamPlayerSpeed = 1000;
  IDVDStreamPlayer* GetStreamPlayer(int) { return &worker; }
  void CloseStream(Audio&, bool) { assert(false); }
  bool OpenAudioStream(CDVDStreamInfo& hint, bool reset) OPEN_AUDIO
};
int main()
{
  Player player;
  using Msg = CDVDMsg;
  player.worker.messages.push_back({Msg::GENERAL_EOF, 0});
  CDVDStreamInfo incoming{86019};
  assert(player.OpenAudioStream(incoming, false));
  assert(player.m_CurrentAudio.syncState == IDVDStreamPlayer::SYNC_STARTING);
  auto& queue = player.worker.messages;
  std::stable_sort(queue.begin(), queue.end(), [](auto a, auto b) { return a.priority > b.priority; });
  auto decoderState = IDVDStreamPlayer::SYNC_INSYNC;
  bool drained = false, reported = false;
  for (auto msg : queue)
  {
    if (msg.type == Msg::GENERAL_EOF)
      drained = true;
    else if (msg.type == Msg::GENERAL_STREAMCHANGE)
    {
      assert(drained);
      decoderState = IDVDStreamPlayer::SYNC_STARTING;
    }
    else if (msg.type == Msg::PLAYER_REQUEST_STATE)
    {
      assert(decoderState == IDVDStreamPlayer::SYNC_STARTING &&
             "a priority state request exposed the outgoing PCM decoder");
      reported = true;
    }
  }
  assert(reported && !player.m_bdjAudioHandoff);
  Player ordinary;
  ordinary.m_bdjAudioHandoff = false;
  assert(ordinary.OpenAudioStream(incoming, false));
  assert(ordinary.worker.messages.back().type == Msg::PLAYER_REQUEST_STATE);
  assert(ordinary.worker.messages.back().priority == 1);
}
'''.replace("OPEN_AUDIO", opened))
