new Vue({
    el: '#app',
    data: {
        version: '0.9.1',
        currentTab: 'dashboard',
        isMobileMenuOpen: false,
        isMobileMenuOpen: false,
        accountStatus: { equity: 0, balance: 0, margin_level: 0, status: 'Disconnected' },
        eaMetrics: { ath: 0, atl: 0, threshold: 0, trade_allowed: true, restriction_reason: 'None' },
        isTradingPaused: false,
        exportPeriod: 30,
        exportPrice: 'BID',
        isExporting: false,
        exportReady: false,
        scanInterval: 4,
        isScanning: false,
        liveConfig: {},
        settingsDirty: false,
        scanResult: null,
        newsConfig: { active_keywords: [], default_keywords: [], active_rss_feeds: [], default_rss_feeds: [] },
        eaConfig: { base_lot_size: 0.01, grid_distance: 100.0, equity_multiplier: 2500, enable_basket_close: false, ath_threshold: 0.15, scan_interval_hours: 4, grid_min: 50, grid_max: 300, grid_step_pct: 25, tp_min: 10, tp_max: 100, tp_t1_mult: 0.6, tp_tier_step: 0.2, tp_tier_max: 1.4 }
    },
    computed: {
        positionCount() {
            const lot = this.eaConfig.base_lot_size || 0.01;
            const mult = this.eaConfig.equity_multiplier || 2500;
            const equity = this.accountStatus.equity || 0;
            const cnt = Math.floor(((equity / mult) * 0.01) / lot + 1e-9);
            return Math.min(Math.max(cnt, 1), 10);
        },
        gates() {
            const m = this.eaMetrics, a = this.accountStatus, g = [];
            g.push({ label: 'Pause', state: this.isTradingPaused ? 'bad' : 'ok', text: this.isTradingPaused ? 'Paused' : 'Auto' });
            g.push({ label: 'Algo', state: m.trade_allowed ? 'ok' : 'bad', text: m.trade_allowed ? 'ON' : 'OFF' });
            g.push({ label: 'Margin', state: (a.margin_level || 0) >= 1000 ? 'ok' : 'bad', text: (a.margin_level || 0) >= 1000 ? 'OK' : (this.fmt(a.margin_level, 0) + '%') });
            const h1ok = !m.g_h1 || m.g_h1 >= (m.g_h1min || 30);
            g.push({ label: 'H1 Trend', state: h1ok ? 'ok' : 'bad', text: h1ok ? ('RSI ' + this.fmt(m.g_h1, 0)) : ('RSI ' + this.fmt(m.g_h1, 0) + ' < ' + this.fmt(m.g_h1min, 0)) });
            g.push({ label: 'ATH Zone', state: (m.g_athpct || 0) <= 85 ? 'ok' : 'bad', text: this.fmt(m.g_athpct, 0) + '%' });
            g.push({ label: 'Exposure', state: (m.g_lots || 0) < (m.g_lotmax || 0) ? 'ok' : 'bad', text: this.fmt(m.g_lots, 2) + '/' + this.fmt(m.g_lotmax, 2) });
            if (!m.pos) g.push({ label: 'Grid', state: 'ok', text: 'first entry' });
            else g.push({ label: 'Grid', state: (m.g_dist || 0) >= (m.g_need || 0) ? 'ok' : 'wait', text: this.fmt(m.g_dist, 0) + ' of ' + this.fmt(m.g_need, 0) + ' pts' });
            g.push({ label: 'Hook', state: (m.restriction_reason === 'None') ? 'ok' : 'wait', text: (m.restriction_reason === 'None') ? 'triggered' : (m.g_hook || 'waiting') });
            return g;
        },
        positions() {
            const m = this.eaMetrics;
            if (!m.pos) return [];
            return m.pos.split(',').filter(x => x).map((pair, i) => {
                const parts = pair.split('|');
                const entry = parseFloat(parts[0]) || 0, tp = parseFloat(parts[1]) || 0, cur = m.g_cur || 0;
                return { entry: entry, tp: tp, tier: i + 1, toTp: tp - cur, floating: cur - entry };
            });
        },
        gridTable() {
            const c = this.eaConfig, atr = this.eaMetrics.atr || 0, R = (this.liveConfig && this.liveConfig.risk_score) || 50;
            const nat = atr * (0.60 + 0.80 * R / 100);
            const G = Math.min(Math.max(nat, c.grid_min || 0), c.grid_max || 9999);
            const rows = [];
            for (let k = 1; k <= Math.max(1, this.positionCount - 1); k++) rows.push({ pair: 'P' + k + '-P' + (k + 1), gap: G * (1 + (c.grid_step_pct || 0) / 100 * (k - 1)) });
            return { G: G, rows: rows };
        },
        tpTable() {
            const c = this.eaConfig, atr = this.eaMetrics.atr || 0, R = (this.liveConfig && this.liveConfig.risk_score) || 50;
            const g = 1.40 - 0.80 * R / 100;
            const rows = [];
            for (let t = 1; t <= this.positionCount; t++) {
                const mult = Math.min((c.tp_t1_mult || 0.6) + (c.tp_tier_step || 0.2) * (t - 1), c.tp_tier_max || 1.4);
                rows.push({ tier: 'T' + t, tp: Math.min(Math.max(atr * mult * g, c.tp_min || 0), c.tp_max || 9999) });
            }
            return rows;
        },
        checkedKeywords() { 
            const defaults = this.newsConfig.default_keywords || [];
            const active = this.newsConfig.active_keywords || [];
            return defaults.filter(k => active.includes(k)).sort(); 
        },
        uncheckedKeywords() { 
            const defaults = this.newsConfig.default_keywords || [];
            const active = this.newsConfig.active_keywords || [];
            return defaults.filter(k => !active.includes(k)).sort(); 
        },
        checkedRssFeeds() { 
            const defaults = this.newsConfig.default_rss_feeds || [];
            const active = this.newsConfig.active_rss_feeds || [];
            return defaults.filter(u => active.includes(u)).sort(); 
        },
        uncheckedRssFeeds() { 
            const defaults = this.newsConfig.default_rss_feeds || [];
            const active = this.newsConfig.active_rss_feeds || [];
            return defaults.filter(u => !active.includes(u)).sort(); 
        }
    },
    methods: {
        fmt(v, d) {
            if (v === null || v === undefined || isNaN(v)) v = 0;
            return Number(v).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
        },
        async saveAsDefault() {
            try {
                await axios.post('/api/v1/config/save_default');
                alert('Current configuration saved as new default for future restarts.');
            } catch (e) { alert('Failed to save default.'); }
        },
        async applyAndSaveDefault() {
            try {
                await axios.post('/api/v1/config/update', this.eaConfig);
                await axios.post('/api/v1/config/save_default');
                this.settingsDirty = false;
                alert('Applied to EA and saved as new default.');
            } catch (e) { alert('Failed to apply/save default.'); }
        },

        getSources() {
            if (!this.scanResult) return [];
            const src = this.scanResult.sources || this.scanResult.verified_sources || this.scanResult.articles || [];
            return Array.isArray(src) ? src.slice(0, 3) : [];
        },
        getHeadline(source) {
            if (typeof source === 'string') return source;
            if (source && source.headline) return source.headline;
            if (source && source.title) return source.title;
            return 'No headline';
        },
        formatNumber(num, decimals = 2) {
            if (num === null || num === undefined) return '0';
            return Number(num).toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
        },
        async fetchStatus() {
            try {
                const res = await axios.get('/api/v1/status');
                this.accountStatus = res.data;
                this.eaMetrics = { ath: res.data.ath || 0, atl: res.data.atl || 0, threshold: res.data.threshold || 0, trade_allowed: res.data.trade_allowed !== false, restriction_reason: res.data.restriction_reason || 'None', grid_eff: res.data.grid_eff || 0, atr: res.data.atr || 0,
                          g_h1: res.data.g_h1 || 0, g_h1min: res.data.g_h1min || 30, g_athpct: res.data.g_athpct || 0,
                          g_lots: res.data.g_lots || 0, g_lotmax: res.data.g_lotmax || 0,
                          g_dist: res.data.g_dist || 0, g_need: res.data.g_need || 0,
                          g_hook: res.data.g_hook || "", g_cur: res.data.g_cur || 0,
                          pos: res.data.pos || "", last_action: res.data.last_action || "" };
                this.isTradingPaused = res.data.is_paused || false;
                if(res.data.last_scan_result) this.scanResult = res.data.last_scan_result;
                if (res.data.ea_config) {
                    const c = res.data.ea_config;
                    this.liveConfig = {
                        base_lot_size: Number(c.LOT), grid_distance: Number(c.GRID_DISTANCE),
                        equity_multiplier: Number(c.EQUITY_MULTIPLIER),
                        tp_low_risk: Number(c.TP_LOW_RISK), tp_med_risk: Number(c.TP_MED_RISK),
                        tp_high_risk: Number(c.TP_HIGH_RISK),
                        enable_basket_close: c.ENABLE_BASKET === 'true',
                        ath_threshold: Number(c.ATH_THRESHOLD),
                        scan_interval_hours: Number(c.SCAN_INTERVAL_HOURS),
                        grid_min: Number(c.GRID_MIN), grid_max: Number(c.GRID_MAX), grid_step_pct: Number(c.GRID_STEP_PCT),
                        tp_min: Number(c.TP_MIN), tp_max: Number(c.TP_MAX),
                        tp_t1_mult: Number(c.TP_T1_MULT), tp_tier_step: Number(c.TP_TIER_STEP), tp_tier_max: Number(c.TP_TIER_MAX),
                        risk_score: Number(c.RISK_SCORE)
                    };
                    if (this.currentTab !== 'settings' || !this.settingsDirty) {
                        this.eaConfig = Object.assign({}, this.eaConfig, this.liveConfig);
                    }
                }
                if (this.isScanning) {
                    const elapsed = Date.now() - (this._scanStartedAt || 0);
                    if (!res.data.scan_in_progress && elapsed > 8000) this.isScanning = false;
                    else if (elapsed > 240000) this.isScanning = false;
                }
            } catch (e) {}
        },
        async fetchPauseStatus() {
            try {
                const res = await axios.get('/api/v1/control/pause');
                this.isTradingPaused = res.data.is_paused;
            } catch (e) {}
        },
        async togglePause() {
            const newState = !this.isTradingPaused;
            this.isTradingPaused = newState; // Optimistic update
            try {
                await axios.post('/api/v1/control/pause?paused=' + newState);
            } catch (e) {
                this.isTradingPaused = !newState; // Revert on error
            }
        },
        async triggerExport() {
            this.isExporting = true; this.exportReady = false;
            try {
                await axios.post('/api/v1/tools/export?days=' + this.exportPeriod + '&price=' + this.exportPrice);
                this.pollExportStatus();
            } catch (e) { this.isExporting = false; }
        },
        pollExportStatus() {
            const poll = setInterval(async () => {
                try {
                    const res = await axios.get('/api/v1/tools/export_status');
                    if (res.data.ready) { clearInterval(poll); this.isExporting = false; this.exportReady = true; }
                } catch (e) { clearInterval(poll); this.isExporting = false; }
            }, 2000);
        },
        downloadCSV() { window.location.href = '/api/v1/tools/download_data'; },
        async triggerScan() {
            this.isScanning = true;
            this._scanStartedAt = Date.now();
            try {
                // Bridge acknowledges immediately; scan runs in background
                await axios.post('/api/v1/news/scan', {}, { timeout: 15000 });
            } catch (e) { /* ignore: status polling will report completion */ }
        },
        async fetchNewsConfig() {
            try {
                const res = await axios.get('/api/v1/news/config');
                this.newsConfig = res.data;
                // Ensure defaults exist for the "Inactive" list to render
                if (!this.newsConfig.default_keywords) this.newsConfig.default_keywords = this.newsConfig.active_keywords || [];
                if (!this.newsConfig.default_rss_feeds) this.newsConfig.default_rss_feeds = this.newsConfig.active_rss_feeds || [];
                if (!this.newsConfig.active_keywords) this.newsConfig.active_keywords = [];
                if (!this.newsConfig.active_rss_feeds) this.newsConfig.active_rss_feeds = [];
            } catch (e) { console.error("Failed to load news config:", e); }
        },
        async saveConfig() {
            try {
                await axios.post('/api/v1/config/update', this.eaConfig);
                this.settingsDirty = false;
                alert('Configuration saved successfully!');
            } catch (e) { alert('Failed to save configuration.'); }
        }
    },
    watch: { currentTab(v) { if (v === 'settings') { this.settingsDirty = false; this.fetchStatus(); } } },
    mounted() {
        this.fetchStatus();
        this.fetchPauseStatus();
        this.fetchNewsConfig();
        setInterval(this.fetchStatus, 2000);
    }
});