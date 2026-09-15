"""过境预测 (TLE + SGP4) 与地面站主控
依赖: pip install skyfield
"""
import datetime as dt

def next_passes(tle_lines, gs_lat, gs_lon, hours=24, min_el=10):
    """返回未来hours内过境窗口列表 [(rise, set, max_el), ...]"""
    from skyfield.api import load, wgs84, EarthSatellite
    ts = load.timescale()
    sat = EarthSatellite(tle_lines[0], tle_lines[1], "PANO-3U", ts)
    gs = wgs84.latlon(gs_lat, gs_lon)
    t0 = ts.now(); t1 = ts.utc(dt.datetime.utcnow() + dt.timedelta(hours=hours))
    times, events = sat.find_events(gs, t0, t1, altitude_degrees=min_el)
    passes = []
    i = 0
    while i < len(events):
        if events[i] == 0:   # 升起
            rise = times[i]
            for j in range(i + 1, len(events)):
                if events[j] == 2:   # 落下
                    peak_t = times[i + 1] if events[i + 1] == 1 else None
                    passes.append((rise.utc_datetime(), times[j].utc_datetime(), peak_t))
                    i = j
                    break
        i += 1
    return passes


def estimate_downlink_bytes(pass_duration_s, bitrate=9600, eff=0.7):
    """单过境可下行字节数估算"""
    return int(pass_duration_s * bitrate / 8 * eff)
