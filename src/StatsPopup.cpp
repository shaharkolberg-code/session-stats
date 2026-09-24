#include "StatsPopup.hpp"
#include "Session.hpp"

using namespace geode::prelude;

namespace ss {

constexpr float LIST_WIDTH = 320.f;
constexpr float ROW_HEIGHT = 26.f;
// Building a node per run gets slow, and nobody scrolls back further than this.
constexpr int MAX_ROWS = 150;

StatsPopup* StatsPopup::create(GJGameLevel* level) {
    auto ret = new StatsPopup();
    if (ret->initPopup(level)) {
        ret->autorelease();
        return ret;
    }
    delete ret;
    return nullptr;
}

bool StatsPopup::initPopup(GJGameLevel* level) {
    if (!Popup::init(360.f, 270.f)) return false;
    m_level = level;

    this->setTitle(std::string(level->m_levelName));

    m_summary = CCLabelBMFont::create("", "goldFont.fnt", LIST_WIDTH / 0.5f, kCCTextAlignmentCenter);
    m_summary->setScale(0.5f);
    m_mainLayer->addChildAtPosition(m_summary, Anchor::Top, {0.f, -50.f});

    m_list = ScrollLayer::create({LIST_WIDTH, 150.f});
    m_list->m_contentLayer->setLayout(ScrollLayer::createDefaultListLayout(3.f));

    auto bg = NineSlice::create("square02b_001.png");
    bg->setColor({0, 0, 0});
    bg->setOpacity(70);
    bg->setContentSize(m_list->getContentSize() + CCSize{6.f, 6.f});
    m_mainLayer->addChildAtPosition(bg, Anchor::Center, {0.f, -15.f});
    m_mainLayer->addChildAtPosition(m_list, Anchor::Center, {-LIST_WIDTH / 2, -15.f - 75.f});

    auto resetSpr = ButtonSprite::create("Reset", "goldFont.fnt", "GJ_button_06.png", 0.8f);
    resetSpr->setScale(0.6f);
    auto resetBtn = CCMenuItemExt::createSpriteExtra(resetSpr, [this](auto) { this->onReset(); });
    m_buttonMenu->addChildAtPosition(resetBtn, Anchor::Bottom, {0.f, 20.f});

    this->refresh();
    return true;
}

static std::pair<const char*, ccColor3B> describe(RunEnd how) {
    switch (how) {
        case RunEnd::Death: return {"Died", {255, 110, 110}};
        case RunEnd::Complete: return {"Complete", {120, 255, 120}};
        case RunEnd::Restart: return {"Restart", {180, 180, 180}};
        case RunEnd::Quit: return {"Quit", {180, 180, 180}};
    }
    return {"", {255, 255, 255}};
}

/// Adds a label to a run row, shrinking it to fit `maxWidth` so columns never overlap.
static CCLabelBMFont* rowLabel(CCNode* row, std::string const& text, float x, float anchorX, float maxWidth, float scale) {
    auto label = CCLabelBMFont::create(text.c_str(), "bigFont.fnt");
    label->limitLabelWidth(maxWidth, scale, 0.1f);
    label->setAnchorPoint({anchorX, 0.5f});
    label->setPosition({x, ROW_HEIGHT / 2});
    row->addChild(label);
    return label;
}

void StatsPopup::refresh() {
    auto& session = sessionFor(m_level);

    std::string summary = fmt::format("Attempts: {}   Time: {}", session.attempts(), formatTime(session.seconds));
    if (!session.platformer) {
        auto best = session.bestFromZero();
        summary += fmt::format("\nBest from 0: {}", best ? formatPercent(*best) : "-");
        if (auto longest = session.longestRun()) {
            summary += fmt::format("   Longest: {}-{}", formatPercent(longest->start), formatPercent(longest->end));
        }
    }
    m_summary->setString(summary.c_str());

    auto content = m_list->m_contentLayer;
    content->removeAllChildren();

    if (session.runs.empty()) {
        auto label = CCLabelBMFont::create(
            "No runs yet this session.", "bigFont.fnt", LIST_WIDTH / 0.4f, kCCTextAlignmentCenter
        );
        label->setScale(0.4f);
        content->addChild(label);
    }

    int shown = 0;
    for (int i = session.attempts() - 1; i >= 0 && shown < MAX_ROWS; --i, ++shown) {
        auto& run = session.runs[i];

        auto row = CCNode::create();
        row->setContentSize({LIST_WIDTH, ROW_HEIGHT});
        row->setAnchorPoint({0.5f, 0.5f});
        auto rowBg = NineSlice::create("square02b_001.png");
        rowBg->setColor({0, 0, 0});
        rowBg->setOpacity(60);
        rowBg->setContentSize({LIST_WIDTH, ROW_HEIGHT});
        rowBg->setAnchorPoint({0.f, 0.f});
        row->addChild(rowBg, -1);

        rowLabel(row, fmt::format("#{}", i + 1), 8.f, 0.f, 32.f, 0.35f)->setColor({200, 200, 200});

        if (!session.platformer) {
            auto range = fmt::format("{} - {}", formatPercent(run.start), formatPercent(run.end));
            rowLabel(row, range, 45.f, 0.f, 110.f, 0.45f);
        }

        auto [text, color] = describe(run.how);
        rowLabel(row, text, 165.f, 0.f, 60.f, 0.35f)->setColor(color);

        if (run.practice) rowLabel(row, "Practice", 232.f, 0.f, 40.f, 0.3f)->setColor({120, 220, 255});

        rowLabel(row, formatTime(run.seconds), LIST_WIDTH - 8.f, 1.f, 38.f, 0.35f);

        content->addChild(row);
    }

    content->updateLayout();
    m_list->scrollToTop();
}

void StatsPopup::onReset() {
    createQuickPopup(
        "Reset Session",
        "Clear this level's <cy>attempts, runs and time</c> for this session?",
        "Cancel", "Reset",
        [self = Ref(this)](auto, bool reset) {
            if (!reset) return;
            resetSession(self->m_level);
            self->refresh();
        }
    );
}

}
