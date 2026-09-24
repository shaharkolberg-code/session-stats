#pragma once

#include <Geode/Geode.hpp>

#include <optional>
#include <string>
#include <vector>

namespace ss {

enum class RunEnd { Death, Complete, Restart, Quit };

struct Run {
    float start = 0.f;
    float end = 0.f;
    double seconds = 0.0; // unpaused time the run lasted
    RunEnd how = RunEnd::Death;
    bool practice = false;
};

/// One level's stats since the game was opened. Kept in memory only.
struct LevelSession {
    bool platformer = false;
    std::vector<Run> runs; // oldest first
    double seconds = 0.0;  // unpaused time spent in the level

    int attempts() const { return static_cast<int>(runs.size()); }
    int completions() const;
    /// Furthest normal-mode run that started at 0%.
    std::optional<float> bestFromZero() const;
    /// Normal-mode run that covered the most distance, from any start position.
    const Run* longestRun() const;
};

LevelSession& sessionFor(GJGameLevel* level);
void resetSession(GJGameLevel* level);

std::string formatTime(double seconds);
std::string formatPercent(float percent);

}
