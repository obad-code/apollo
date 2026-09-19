import os

import clips


def packet(i, keyframe=False, when=None):
    return (b"x" * 10, i, keyframe, when if when is not None else i / 30.0)


def test_ring_drops_old_packets():
    ring = clips.Ring(seconds=2, slack=1)
    for i in range(300):                       # ten seconds at 30 fps
        ring.add(packet(i), i / 30.0)
    kept = ring.items()
    assert len(kept) < 100                     # three seconds' worth at most
    assert ring.span() <= 3.0
    assert ring.newest()[0][1] == 299


def test_window_starts_at_a_keyframe():
    packets = [packet(i, keyframe=(i % 30 == 0)) for i in range(120)]
    chosen = clips.window(packets, start=2.2)   # 2.2s in: keyframe at 60 (2.0s)
    assert chosen[0][1] == 60 and chosen[0][2] is True
    assert chosen[-1][1] == 119


def test_window_shorter_than_asked():
    packets = [packet(i, keyframe=(i % 30 == 0)) for i in range(45)]
    chosen = clips.window(packets, start=-10.0)   # asked for more than we hold
    assert chosen[0][1] == 0 and len(chosen) == 45


def test_window_with_no_keyframe_is_empty():
    assert clips.window([packet(i) for i in range(10)], start=0.0) == []


def test_clip_path_is_sortable_and_legal(tmp_path):
    import datetime
    path = clips.clip_path(datetime.datetime(2026, 9, 20, 2, 11, 7), folder_path=str(tmp_path))
    assert os.path.basename(path) == "Apollo 2026-09-20 02-11-07.mp4"
    assert os.path.isdir(os.path.dirname(path))


def test_folder_is_under_videos():
    assert clips.folder().replace("\\", "/").endswith("Videos/Apollo's Clips")
