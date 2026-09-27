# Profiling Python Code

use https://github.com/emeryberger/scalene

Run with:

```
scalene main.py {TronView args here}
```

# Built in frame profiler

In view mode press `d` to cycle debug mode:

- debug 1: bottom left shows `FPS | draw | present | idle` averages.
  - `draw` = time spent drawing all screen modules.
  - `present` = time spent in `pygame.display.update()` (scales with window pixel count).
  - `idle` = time the frame limiter waited. Near 0 means the program is render bound.
- debug 2: also shows each module's draw time (in ms) at the bottom left of the module.

# Performance guidelines (keep these when writing/changing modules)

These came out of getting the Epic Optix HUD to 60+ FPS on a Raspberry Pi 5.

- Only one display presentation per frame. The main loop calls `pygame.display.update()`.
  Modules must never call `pygame.display.flip()` or `update()`.
- Avoid full screen / full module temporary surfaces that get cleared and blitted every frame.
  Use `Module.getDrawSurface(pos)` to draw directly onto the display (it returns a cached
  subsurface of the screen at the module position, with module local coordinates and clipping).
  See `horizon_v2`, `cdi`, `gcross`, `trafficscope`, `traffic_bar`.
- Cache static graphics (scales, rings, labels) and rendered text surfaces. Don't call
  `font.render()` for text that doesn't change.
- Rotate/scale only the smallest graphic needed, and cache the results (see `rollindicator`).
- Compute trig once per frame, not once per line.
- Keep expensive calculations (geodesic distance/bearing, declination) out of the draw loop.
  They belong in the input thread or should be cached (see `GPSData.get_mag_decl()`).
- Window size matters: 1280x720 is ~56% fewer pixels than 1920x1080, and the display update
  cost scales with it. The Epic Optix HUD uses `window=1280,720` and `maxframerate=60`.
- Keep units and references consistent:
  - distances in the dataship are statute miles, speeds are mph.
  - GPS ground track and ADS-B bearings are TRUE; IMU heading is MAGNETIC. Add declination
    (`GPSData.get_mag_decl()`) to magnetic heading before comparing it with track/bearing.
  - ADS-B traffic altitude and the GDL90 ownship report altitude are PRESSURE altitude.
    GPS (geometric) altitude is a different datum; don't mix them when computing altDiff.
- Profile before optimizing (built in profiler above, or scalene).
