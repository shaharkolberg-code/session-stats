#pragma once

#include <Geode/Geode.hpp>

namespace ss {

/// Summary and run history for one level's session.
class StatsPopup : public geode::Popup {
public:
    static StatsPopup* create(GJGameLevel* level);

protected:
    geode::Ref<GJGameLevel> m_level;
    geode::ScrollLayer* m_list = nullptr;
    cocos2d::CCLabelBMFont* m_summary = nullptr;

    bool initPopup(GJGameLevel* level);
    void refresh();
    void onReset();
};

}
