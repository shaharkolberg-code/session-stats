#include "Session.hpp"

#include <unordered_map>

using namespace geode::prelude;

namespace ss {

// A run that starts this close to 0% counts as a run from 0.
constexpr float FROM_ZERO_EPSILON = 0.5f;

static std::unordered_map<std::string, LevelSession> s_sessions;

static std::string keyFor(GJGameLevel* level) {
    int type = static_cast<int>(level->m_levelType);
    if (int id = level->m_levelID.value(); id > 0) return fmt::format("{}:{}", type, id);
    // editor and other unuploaded levels have no ID, so fall back to the name
    return fmt::format("{}:{}", type, std::string(level->m_levelName));
}

int LevelSession::completions() const {
    int count = 0;
    for (auto& run : runs) {
        if (run.how == RunEnd::Complete && !run.practice) ++count;
    }
    return count;
}

std::optional<float> LevelSession::bestFromZero() const {
    std::optional<float> best;
    for (auto& run : runs) {
        if (run.practice || run.start > FROM_ZERO_EPSILON) continue;
        if (!best || run.end > *best) best = run.end;
    }
    return best;
}

const Run* LevelSession::longestRun() const {
    const Run* best = nullptr;
    for (auto& run : runs) {
        if (run.practice) continue;
        if (!best || run.end - run.start > best->end - best->start) best = &run;
    }
    return best;
}

LevelSession& sessionFor(GJGameLevel* level) {
    auto& session = s_sessions[keyFor(level)];
    session.platformer = level->isPlatformer();
    return session;
}

void resetSession(GJGameLevel* level) {
    auto& session = sessionFor(level);
    session.runs.clear();
    session.seconds = 0.0;
}

std::string formatTime(double seconds) {
    int total = static_cast<int>(seconds);
    int h = total / 3600, m = total / 60 % 60, s = total % 60;
    if (h > 0) return fmt::format("{}:{:02}:{:02}", h, m, s);
    return fmt::format("{}:{:02}", m, s);
}

std::string formatPercent(float percent) {
    return fmt::format("{}%", static_cast<int>(percent));
}

}
