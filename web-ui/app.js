new Vue({
    el: '#app',
    data: {
        version: '0.3.0',
        currentTab: 'dashboard',
        isMobileMenuOpen: false,
        isMobileMenuOpen: false,
        accountStatus: { equity: 0, balance: 0, margin_level: 0, status: 'Disconnected' },
        eaMetrics: { ath: 0, atl: 0, threshold: 0, trade_allowed: true, restriction_reason: 'None' },
        isTradingPaused: false,
        exportPeriod: 30,
        isExporting: false,
        exportReady: false,
        scanInterval: 4,
        isScanning: false,
        liveConfig: {},
        settingsDirty: false,
        scanResult: null,
        newsConfig: { active_keywords: [], default_keywords: [], active_rss_feeds: [], default_rss_feeds: [] },
        eaConfig: { base_lot_size: 0.01, grid_distance: 100.0, equity_multiplier: 2500, enable_basket_close: false, ath_threshold: 0.15, scan_interval_hours: 4 }
    },
    computed: {
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
                this.eaMetrics = { ath: res.data.ath || 0, atl: res.data.atl || 0, threshold: res.data.threshold || 0, trade_allowed: res.data.trade_allowed !== false, restriction_reason: res.data.restriction_reason || 'None', grid_eff: res.data.grid_eff || 0, atr: res.data.atr || 0 };
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
                await axios.post('/api/v1/tools/export?days=' + this.exportPeriod);
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