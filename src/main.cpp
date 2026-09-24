#include "Session.hpp"
#include "StatsPopup.hpp"

#include <Geode/Geode.hpp>
#include <Geode/modify/PlayLayer.hpp>
#include <Geode/modify/PauseLayer.hpp>

#include <algorithm>
#include <cmath>

using namespace geode::prelude;

constexpr float HUD_MARGIN = 5.f;
// A restart this soon after a run began, with no progress, isn't an attempt.
// GD resets the level once while it loads, which would otherwise count.
constexpr double MIN_RESTART_SECONDS = 1.0;

class $modify(SSPlayLayer, PlayLayer) {
    struct Fields {
        ss::LevelSession* m_session = nullptr;
        CCLabelBMFont* m_hud = nullptr;
        bool m_runOpen = false;
        float m_runStart = 0.f;
        double m_runSeconds = 0.0;
        int m_shownSecond = -1;
    };

    bool init(GJGameLevel* level, bool useReplay, bool dontCreateObjects) {
        if (!PlayLayer::init(level, useReplay, dontCreateObjects)) return false;

        auto fields = m_fields.self();
        fields->m_session = &ss::sessionFor(level);

        auto hud = CCLabelBMFont::create("", "bigFont.fnt");
        hud->setScale(0.35f);
        hud->setID("session-hud"_spr);
        this->addChild(hud, 100);
        fields->m_hud = hud;

        this->openRun();
        this->updateHud();
        this->schedule(schedule_selector(SSPlayLayer::onSessionTick));
        return true;
    }

    void resetLevel() {
        this->closeRun(ss::RunEnd::Restart);
        PlayLayer::resetLevel();
        this->openRun();
    }

    void destroyPlayer(PlayerObject* player, GameObject* object) {
        // GD kills the player with this object once on load as an anticheat check
        if (object == m_anticheatSpike) return PlayLayer::destroyPlayer(player, object);

        bool wasDead = player->m_isDead;
        PlayLayer::destroyPlayer(player, object);
        // noclip and similar mods keep the player alive, so check afterwards
        if (!wasDead && player->m_isDead) this->closeRun(ss::RunEnd::Death);
    }

    void levelComplete() {
        this->closeRun(ss::RunEnd::Complete);
        PlayLayer::levelComplete();
    }

    void onQuit() {
        this->closeRun(ss::RunEnd::Quit);
        PlayLayer::onQuit();
    }

    float currentPercent() {
        // can be NaN before the level has finished loading
        float percent = this->getCurrentPercent();
        return std::isfinite(percent) ? std::clamp(percent, 0.f, 100.f) : 0.f;
    }

    void openRun() {
        auto fields = m_fields.self();
        fields->m_runOpen = true;
        fields->m_runStart = this->currentPercent();
        fields->m_runSeconds = 0.0;
    }

    void closeRun(ss::RunEnd how) {
        auto fields = m_fields.self();
        if (!fields->m_runOpen || !fields->m_session) return;
        fields->m_runOpen = false;

        float end = how == ss::RunEnd::Complete ? 100.f : this->currentPercent();

        if (how == ss::RunEnd::Restart || how == ss::RunEnd::Quit) {
            if (!Mod::get()->getSettingValue<bool>("count-restarts")) return;
            bool progressed = end > fields->m_runStart || fields->m_runSeconds >= MIN_RESTART_SECONDS;
            if (!progressed) return;
        }

        fields->m_session->runs.push_back({
            .start = fields->m_runStart,
            .end = end,
            .seconds = fields->m_runSeconds,
            .how = how,
            .practice = m_isPracticeMode,
        });
        this->updateHud();
    }

    void onSessionTick(float dt) {
        if (m_isPaused) return;
        auto fields = m_fields.self();
        if (!fields->m_session) return;

        fields->m_session->seconds += dt;
        if (fields->m_runOpen) fields->m_runSeconds += dt;

        if (static_cast<int>(fields->m_session->seconds) != fields->m_shownSecond) this->updateHud();
    }

    void updateHud() {
        auto fields = m_fields.self();
        auto hud = fields->m_hud;
        auto session = fields->m_session;
        if (!hud || !session) return;

        fields->m_shownSecond = static_cast<int>(session->seconds);

        // settings are re-read here so changes apply without restarting the level
        auto mod = Mod::get();
        hud->setVisible(mod->getSettingValue<bool>("show-hud"));
        hud->setOpacity(static_cast<GLubyte>(mod->getSettingValue<int64_t>("hud-opacity")));

        std::string text = fmt::format("Attempts: {}", session->attempts());
        if (!session->platformer) {
            if (auto best = session->bestFromZero()) {
                text += fmt::format("\nBest: {}", ss::formatPercent(*best));
            }
            auto longest = session->longestRun();
            if (longest && longest->start > 0.5f) {
                text += fmt::format(
                    "\nLongest: {}-{}", ss::formatPercent(longest->start), ss::formatPercent(longest->end)
                );
            }
        }
        if (int done = session->completions()) text += fmt::format("\nCompletions: {}", done);
        text += fmt::format("\nTime: {}", ss::formatTime(session->seconds));
        hud->setString(text.c_str());

        auto corner = mod->getSettingValue<std::string>("hud-corner");
        bool top = corner.starts_with("Top");
        bool left = corner.ends_with("Left");
        auto win = CCDirector::get()->getWinSize();
        hud->setAlignment(left ? kCCTextAlignmentLeft : kCCTextAlignmentRight);
        hud->setAnchorPoint({left ? 0.f : 1.f, top ? 1.f : 0.f});
        hud->setPosition({
            left ? HUD_MARGIN : win.width - HUD_MARGIN,
            top ? win.height - HUD_MARGIN : HUD_MARGIN,
        });
    }
};

class $modify(SSPauseLayer, PauseLayer) {
    void customSetup() {
        PauseLayer::customSetup();

        auto playLayer = PlayLayer::get();
        if (!playLayer || !playLayer->m_level) return;

        CCNode* spr = CCSprite::createWithSpriteFrameName("GJ_statsBtn_001.png");
        if (spr) spr->setScale(0.6f);
        else spr = ButtonSprite::create("Stats");

        auto btn = CCMenuItemExt::createSpriteExtra(spr, [level = playLayer->m_level](auto) {
            ss::StatsPopup::create(level)->show();
        });
        btn->setID("session-stats-button"_spr);

        if (auto menu = this->getChildByID("right-button-menu")) {
            menu->addChild(btn);
            menu->updateLayout();
            return;
        }

        log::warn("right-button-menu not found, placing session stats button manually");
        auto menu = CCMenu::create();
        menu->setID("session-stats-menu"_spr);
        auto win = CCDirector::get()->getWinSize();
        menu->setPosition({win.width - 30.f, win.height / 2});
        menu->addChild(btn);
        this->addChild(menu, 10);
    }
};
