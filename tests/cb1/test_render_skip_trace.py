"""Exercise the shipped render queue counter and the selected/discarded PTS trace."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

from test_native_video_source import TREE


class RenderSkipTrace(unittest.TestCase):
    def test_skip_reports_discarded_identity_and_initial_queue_depth(self):
        root = TREE / "xbmc/cores/VideoPlayer/VideoRenderers"
        header = (root / "RenderManager.h").read_text()
        source = (root / "RenderManager.cpp").read_text()
        counter = re.search(r"^\s*(?:std::atomic<int>|int) m_QueueSkip(?: = 0|\{0\});",
                            header, re.M).group().strip()
        getter = re.search(r"int GetSkippedFrames\(\).*?\}", header).group()
        start = source.index("    // skip late frames")
        end = source.index("    const double lateness", start)
        block = source[start:end]
        harness = r"""
#include <atomic>
#include <array>
#include <cassert>
#include <cstdio>
#include <deque>
#include <type_traits>
#include <vector>
constexpr int LOGDEBUG=1, LOGAVTIMING=2;
struct CLog {
  struct Skip {
    double dropped, selected, deadline;
    size_t queued;
    int total;
  };
  static inline std::vector<Skip> events;
  static void LogFC(int, int, const char*, double dropped, double selected,
                    double deadline, size_t queued, int total) {
    events.push_back({dropped,selected,deadline,queued,total});
  }
};
struct CRenderManager {
  COUNTER
  GETTER
  static_assert(std::is_same_v<decltype(m_QueueSkip),std::atomic<int>>);
  struct Picture {double pts;};
  std::array<Picture,4> m_Queue{{{100},{200},{300},{400}}};
  std::deque<int> m_queued{0,1,2,3},m_discard;
  int m_presentsourcePast=-1;
  void Select(int idx,double latePts) {
    (void)latePts;
    BLOCK
  }
};
int main() {
  CRenderManager renderer;
  renderer.Select(3,490);
  assert(renderer.GetSkippedFrames()==2);
  assert(renderer.m_presentsourcePast==2 && renderer.m_queued.front()==3);
  assert(CLog::events.size()==2);
  assert(CLog::events[0].dropped==100 && CLog::events[1].dropped==200);
  assert(CLog::events[0].selected==400 && CLog::events[1].selected==400);
  assert(CLog::events[0].deadline==490 && CLog::events[1].deadline==490);
  assert(CLog::events[0].queued==4 && CLog::events[1].queued==4);
  assert(CLog::events[0].total==1 && CLog::events[1].total==2);
  CLog::events.clear();
  CRenderManager single;
  single.m_queued={0,1};
  single.Select(1,290);
  assert(single.GetSkippedFrames()==0 && CLog::events.empty());
  CRenderManager triple;
  triple.m_queued={0,1,2};
  triple.Select(2,390);
  assert(triple.GetSkippedFrames()==1 && CLog::events.size()==1);
  assert(CLog::events[0].dropped==100 && CLog::events[0].selected==300);
  assert(CLog::events[0].queued==3 && CLog::events[0].total==1);
  CLog::events.clear();
  renderer.Select(3,510);
  assert(renderer.GetSkippedFrames()==2 && CLog::events.empty());
}
"""
        program = (harness.replace("COUNTER", counter)
                   .replace("GETTER", getter).replace("BLOCK", block))
        with tempfile.TemporaryDirectory() as temporary:
            binary = Path(temporary) / "skip-trace"
            subprocess.run(["c++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                            "-x", "c++", "-", "-o", str(binary)],
                           input=program, text=True, check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    unittest.main()
