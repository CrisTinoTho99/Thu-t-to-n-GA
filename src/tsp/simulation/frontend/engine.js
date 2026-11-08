/** Deterministic timeline sampling and a clock-injected playback controller. */
const SPEEDS = [0.5, 1, 2, 4];
const STATES = new Set(["idle", "playing", "paused", "stopped", "completed"]);
const clamp = (value, low, high) => Math.max(low, Math.min(high, value));

/** Derive every visible value from the same simulation cursor. */
export function snapshotAt(schedule, time, state = "paused") {
  if (!Number.isFinite(time)) throw new RangeError("Simulation time must be finite.");
  if (!STATES.has(state)) throw new RangeError("Unknown playback state.");
  const idle = state === "idle";
  const duration = schedule.total_duration;
  const t = idle ? 0 : clamp(time, 0, duration);
  const complete = !idle && t >= duration;
  const depot = schedule.locations[schedule.depot_index];
  const customers = schedule.locations.length - 1;
  const statuses = schedule.locations.map((_, index) => index === schedule.depot_index ? "Warehouse" : "Pending");
  let x = depot.x;
  let y = depot.y;
  let heading = schedule.phases[0]?.heading ?? 0;
  let phase = "at_depot";
  let destination = null;
  let traveled = 0;
  let delivered = 0;
  if (!idle) {
    for (const stop of schedule.stops) {
      if (stop.delivery_time <= t) {
        statuses[stop.index] = "Delivered";
        delivered += 1;
      }
    }
    const active = complete ? null : schedule.phases.find(item => item.end_time > t);
    if (active) {
      const start = schedule.locations[active.start_index];
      const end = schedule.locations[active.end_index];
      destination = active.end_index;
      heading = active.heading;
      if (active.kind === "travel") {
        const length = active.end_time - active.start_time;
        const fraction = length > 0 ? clamp((t - active.start_time) / length, 0, 1) : 1;
        x = start.x + (end.x - start.x) * fraction;
        y = start.y + (end.y - start.y) * fraction;
        traveled = active.distance_start + (active.distance_end - active.distance_start) * fraction;
        phase = "moving";
        if (destination !== schedule.depot_index && statuses[destination] !== "Delivered") statuses[destination] = "In Transit";
      } else {
        x = end.x;
        y = end.y;
        traveled = active.distance_end;
        phase = "delivering";
        if (destination !== schedule.depot_index) statuses[destination] = "Delivering";
      }
    } else {
      traveled = schedule.total_distance;
      heading = schedule.phases.at(-1)?.heading ?? heading;
    }
  }
  traveled = clamp(traveled, 0, schedule.total_distance);
  return {
    x, y, heading, phase, destination_index: destination,
    delivered_count: delivered,
    remaining_count: customers - delivered,
    distance_traveled: traveled,
    remaining_distance: Math.max(0, schedule.total_distance - traveled),
    progress_percent: idle ? 0 : (duration > 0 ? 100 * t / duration : 100),
    distance_progress_percent: schedule.total_distance > 0 ? 100 * traveled / schedule.total_distance : (complete ? 100 : 0),
    elapsed: t,
    remaining_time: Math.max(0, duration - t),
    statuses,
    visible_events: idle ? [] : schedule.events.filter(event => event.time <= t).map(event => event.id),
  };
}

/** Playback uses milliseconds from an injected monotonic clock; the route uses seconds. */
export class Playback {
  constructor(schedule, checkpoint = null, now = () => performance.now()) {
    if (!schedule || !Number.isFinite(schedule.total_duration) || schedule.total_duration < 0) throw new TypeError("A finite simulation schedule is required.");
    this.schedule = schedule;
    this.now = now;
    this.time = 0;
    this.speed = 1;
    this.state = "idle";
    this.started = false;
    this.sequence = 0;
    if (checkpoint && checkpoint.route_key === schedule.route_key && Number.isFinite(checkpoint.time)) {
      this.time = clamp(checkpoint.time, 0, schedule.total_duration);
      this.speed = SPEEDS.includes(checkpoint.speed) ? checkpoint.speed : 1;
      this.started = checkpoint.started === true;
      this.sequence = Number.isSafeInteger(checkpoint.sequence) && checkpoint.sequence >= 0 ? checkpoint.sequence : 0;
      this.state = this.started ? (this.time >= schedule.total_duration ? "completed" : "paused") : "idle";
      if (!this.started) this.time = 0;
    }
    this.anchorTime = this.time;
    this.anchorNow = this.now();
  }

  snapshot() { return snapshotAt(this.schedule, this.time, this.state); }

  tick(now = this.now()) {
    if (!Number.isFinite(now)) throw new RangeError("Playback clock must be finite.");
    if (this.state === "playing") {
      this.time = clamp(this.anchorTime + Math.max(0, now - this.anchorNow) * this.speed / 1000, 0, this.schedule.total_duration);
      if (this.time >= this.schedule.total_duration) {
        this.state = "completed";
        this.sequence += 1;
      }
    }
    return this.snapshot();
  }

  play(now = this.now()) {
    if (this.state === "playing" || this.state === "completed") return this.snapshot();
    this.started = true;
    this.state = "playing";
    this.anchorTime = this.time;
    this.anchorNow = now;
    this.sequence += 1;
    return this.tick(now);
  }

  pause(now = this.now()) {
    this.tick(now);
    if (this.state === "playing") {
      this.state = "paused";
      this.sequence += 1;
    }
    return this.snapshot();
  }

  stop(now = this.now()) {
    this.tick(now);
    if (!["idle", "completed", "stopped"].includes(this.state)) {
      this.state = "stopped";
      this.sequence += 1;
    }
    return this.snapshot();
  }

  restart() {
    this.time = 0;
    this.started = false;
    this.state = "idle";
    this.anchorTime = 0;
    this.anchorNow = this.now();
    this.sequence += 1;
    return this.snapshot();
  }

  seek(time) {
    if (!Number.isFinite(time)) throw new RangeError("Seek time must be finite.");
    this.time = clamp(time, 0, this.schedule.total_duration);
    this.started = true;
    this.state = this.time >= this.schedule.total_duration ? "completed" : "paused";
    this.anchorTime = this.time;
    this.anchorNow = this.now();
    this.sequence += 1;
    return this.snapshot();
  }

  setSpeed(speed, now = this.now()) {
    if (!SPEEDS.includes(speed)) throw new RangeError("Playback speed must be 0.5, 1, 2 or 4.");
    this.tick(now);
    if (speed !== this.speed) {
      this.speed = speed;
      this.anchorTime = this.time;
      this.anchorNow = now;
      this.sequence += 1;
    }
    return this.snapshot();
  }

  checkpoint() {
    return {route_key: this.schedule.route_key, time: this.time, speed: this.speed,
      state: this.state, started: this.started, sequence: this.sequence};
  }
}
