const { createApp } = Vue;
createApp({
    data() {
        return {
            sidebarOpen: false, currentTab: 'dashboard', userEmail: null,
            config: { branding: { logo_url: '', app_name: 'Loading...', tagline: '' } },
            version: '0.1.0',
            account: { equity: 0, balance: 0, margin_level: 0, status: 'Disconnected', active_positions: 0 },
            news: { risk_score: 0, bias: 'Neutral/Caution', primary_driver: 'None', recommendation: 'Pending', verified_sources: [] },
            configForm: { base_lot_size: 0.01, grid_distance: 50, equity_multiplier: 2500, tp_low_risk: 20, tp_med_risk: 15, tp_high_risk: 10 },
            newsConfig: { default_keywords: [], active_keywords: [], default_rss_feeds: [], active_rss_feeds: [], risk_threshold_low: 40, risk_threshold_high: 70 },
            newKeyword: '', newRssUrl: '', rssValidationMsg: ''
        }
    },
    mounted() { this.loadConfig(); this.fetchStatus(); this.fetchNews(); this.fetchNewsConfig(); setInterval(() => { this.fetchStatus(); this.fetchNews(); }, 5000); },
    computed: {
        checkedKeywords() {
            if (!this.newsConfig.default_keywords) return [];
            return this.newsConfig.default_keywords
                .filter(k => this.newsConfig.active_keywords.includes(k))
                .sort((a, b) => a.localeCompare(b));
        },
        uncheckedKeywords() {
            if (!this.newsConfig.default_keywords) return [];
            return this.newsConfig.default_keywords
                .filter(k => !this.newsConfig.active_keywords.includes(k))
                .sort((a, b) => a.localeCompare(b));
        },
        checkedRssFeeds() {
            const defaults = this.newsConfig.default_rss_feeds || [];
            const customs = this.newsConfig.active_rss_feeds.filter(u => !defaults.includes(u)) || [];
            const allFeeds = [...defaults, ...customs];
            return allFeeds
                .filter(u => this.newsConfig.active_rss_feeds.includes(u))
                .sort((a, b) => a.localeCompare(b));
        },
        uncheckedRssFeeds() {
            const defaults = this.newsConfig.default_rss_feeds || [];
            const customs = this.newsConfig.active_rss_feeds.filter(u => !defaults.includes(u)) || [];
            const allFeeds = [...defaults, ...customs];
            return allFeeds
                .filter(u => !this.newsConfig.active_rss_feeds.includes(u))
                .sort((a, b) => a.localeCompare(b));
        }
    },
    methods: {
        toggleSidebar() { this.sidebarOpen = !this.sidebarOpen; },
        closeSidebar() { this.sidebarOpen = false; },
        async loadConfig() { try { this.config = (await axios.get('/static/config.json')).data; } catch (e) {} },
        async fetchStatus() { try { this.account = (await axios.get('/api/v1/status')).data; } catch (e) {} },
        async fetchNews() { try { this.news = (await axios.get('/api/v1/news/status')).data; } catch (e) {} },
        async fetchNewsConfig() { 
            try { 
                this.newsConfig = (await axios.get('/api/v1/news/config')).data; 
                // Ensure arrays exist
                if(!this.newsConfig.active_keywords) this.newsConfig.active_keywords = [];
                if(!this.newsConfig.active_rss_feeds) this.newsConfig.active_rss_feeds = [];
            } catch (e) {} 
        },
        async triggerScan() { 
            try { await axios.get('/api/v1/news/scan'); alert('✅ Scan initiated!'); setTimeout(() => { this.fetchNews(); }, 5000); } 
            catch (e) { alert('❌ Failed to trigger scan: ' + (e.response ? e.response.data.detail : e.message)); } 
        },
        async saveConfig() { 
            try { await axios.post('/api/v1/config/update', this.configForm); alert('✅ EA Configuration updated!'); } 
            catch (e) { alert('❌ Failed to update EA config.'); } 
        },
        async validateRss() {
            if(!this.newRssUrl) return;
            this.rssValidationMsg = 'Validating...';
            try {
                const res = await axios.post('/api/v1/news/validate_url', {url: this.newRssUrl});
                if(res.data.valid) {
                    this.rssValidationMsg = '✅ Valid: ' + res.data.title;
                    this.newsConfig.active_rss_feeds.push(this.newRssUrl);
                    this.newRssUrl = '';
                } else {
                    this.rssValidationMsg = '❌ Invalid: ' + res.data.error;
                }
            } catch(e) { this.rssValidationMsg = '❌ Validation failed.'; }
        },
        addKeyword() {
            if(this.newKeyword && !this.newsConfig.active_keywords.includes(this.newKeyword)) {
                this.newsConfig.active_keywords.push(this.newKeyword);
                if(!this.newsConfig.default_keywords.includes(this.newKeyword)) {
                    this.newsConfig.default_keywords.push(this.newKeyword);
                }
                this.newKeyword = '';
            }
        },
        async saveNewsConfig(saveDefault) {
            try { 
                const payload = {...this.newsConfig, save_as_default: saveDefault};
                await axios.post('/api/v1/news/config', payload); 
                alert(saveDefault ? '✅ News config saved as default!' : '✅ News config updated for this session!'); 
                this.sortSelectedFirst();
            } catch (e) { alert('❌ Failed to update news config.'); } 
        }
    }
}).mount('#app');