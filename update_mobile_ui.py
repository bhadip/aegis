import os

os.chdir('/home/tom/aegis')

# 1. Update app.js to include sidebar toggle logic
app_js = """const { createApp } = Vue;

createApp({
    data() {
        return {
            sidebarOpen: false,
            currentTab: 'dashboard',
            userEmail: null,
            config: { branding: { logo_url: '', app_name: 'Loading...', tagline: '' } },
            account: { equity: 0, margin_level: 0, status: 'Loading...', active_positions: 0 },
            news: { risk_score: 0, bias: 'Neutral/Caution', primary_driver: 'None', recommendation: 'Pending', verified_sources: [] },
            configForm: { base_lot_size: 0.01, grid_distance_points: 200, max_total_exposure_lots: 0.10 },
            newsConfigForm: { keywords: 'Tariff, Fed, War, Inflation, Recession, Nasdaq', risk_threshold_low: 40, risk_threshold_high: 70 }
        }
    },
    mounted() {
        this.loadConfig();
        this.fetchStatus();
        this.fetchNews();
        this.fetchNewsConfig();
    },
    methods: {
        toggleSidebar() {
            this.sidebarOpen = !this.sidebarOpen;
        },
        closeSidebar() {
            this.sidebarOpen = false;
        },
        async loadConfig() {
            try {
                const response = await axios.get('/static/config.json');
                this.config = response.data;
            } catch (error) { console.error('Failed to load config:', error); }
        },
        async fetchStatus() {
            try {
                const response = await axios.get('/api/v1/status');
                this.account = response.data;
            } catch (error) { console.error('Failed to fetch status:', error); }
        },
        async fetchNews() {
            try {
                const response = await axios.get('/api/v1/news/status');
                this.news = response.data;
            } catch (error) { console.error('Failed to fetch news:', error); }
        },
        async fetchNewsConfig() {
            try {
                const response = await axios.get('/api/v1/news/config');
                this.newsConfigForm = response.data;
            } catch (error) { console.error('Failed to fetch news config:', error); }
        },
        async triggerScan() {
            try {
                await axios.get('/api/v1/news/scan');
                alert('✅ Scan initiated! Data will update in ~5 seconds.');
                setTimeout(() => { this.fetchNews(); }, 5000);
            } catch (error) { alert('❌ Failed to trigger scan.'); }
        },
        async saveConfig() {
            try {
                await axios.post('/api/v1/config/update', this.configForm);
                alert('✅ EA Configuration updated successfully!');
            } catch (error) { alert('❌ Failed to update EA config.'); }
        },
        async saveNewsConfig() {
            try {
                await axios.post('/api/v1/news/config', this.newsConfigForm);
                alert('✅ News Intelligence parameters updated!');
                this.fetchNewsConfig();
            } catch (error) { alert('❌ Failed to update news config.'); }
        }
    }
}).mount('#app');"""

with open('web-ui/app.js', 'w') as f:
    f.write(app_js)

# 2. Update index.html with mobile-responsive layout
index_html = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AEGIS Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/axios/dist/axios.min.js"></script>
    <script>tailwind.config = { darkMode: 'class', theme: { extend: { colors: { brand: '#0ea5e9' } } } }</script>
</head>
<body class="bg-gray-900 text-gray-100 font-sans antialiased">
    <div id="app" class="h-screen bg-gray-900 text-gray-100 font-sans antialiased overflow-hidden flex flex-col md:flex-row">
        
        <!-- Mobile Header -->
        <header class="md:hidden bg-gray-800 p-4 flex justify-between items-center border-b border-gray-700 z-40 shrink-0">
            <div class="flex items-center space-x-3">
                <img :src="config.branding.logo_url" class="h-8 w-8 rounded-lg" alt="Logo">
                <h1 class="text-lg font-bold text-brand">{{ config.branding.app_name }}</h1>
            </div>
            <button @click="toggleSidebar" class="text-gray-300 hover:text-white focus:outline-none">
                <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
                </svg>
            </button>
        </header>

        <!-- Mobile Overlay -->
        <div v-if="sidebarOpen" @click="closeSidebar" class="fixed inset-0 bg-black bg-opacity-50 z-40 md:hidden"></div>

        <!-- Sidebar -->
        <aside :class="sidebarOpen ? 'translate-x-0' : '-translate-x-full'" class="fixed inset-y-0 left-0 z-50 w-64 bg-gray-800 border-r border-gray-700 flex flex-col transition-transform duration-200 ease-in-out md:static md:translate-x-0 shrink-0">
            <div class="p-6 hidden md:flex items-center space-x-3">
                <img :src="config.branding.logo_url" class="h-10 w-10 rounded-lg" alt="Logo">
                <div>
                    <h1 class="text-xl font-bold text-brand">{{ config.branding.app_name }}</h1>
                    <p class="text-xs text-gray-400">{{ config.branding.tagline }}</p>
                </div>
            </div>
            <nav class="flex-1 px-4 space-y-2 mt-4 md:mt-0">
                <a href="#" @click.prevent="currentTab = 'dashboard'; closeSidebar()" :class="{'bg-brand text-white': currentTab==='dashboard'}" class="block px-4 py-2 rounded-md hover:bg-gray-700">Dashboard</a>
                <a href="#" @click.prevent="currentTab = 'news'; closeSidebar()" :class="{'bg-brand text-white': currentTab==='news'}" class="block px-4 py-2 rounded-md hover:bg-gray-700">News Intelligence</a>
                <a href="#" @click.prevent="currentTab = 'settings'; closeSidebar()" :class="{'bg-brand text-white': currentTab==='settings'}" class="block px-4 py-2 rounded-md hover:bg-gray-700">Settings</a>
            </nav>
            <div class="p-4 border-t border-gray-700 text-xs text-gray-500">
                User: {{ userEmail || 'Unauthenticated' }}
            </div>
        </aside>

        <!-- Main Content -->
        <main class="flex-1 overflow-y-auto p-4 md:p-8">
            <!-- Dashboard Tab -->
            <div v-if="currentTab === 'dashboard'">
                <h2 class="text-xl md:text-2xl font-bold mb-4 md:mb-6">Account Status</h2>
                <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 md:gap-6 mb-6 md:mb-8">
                    <div class="bg-gray-800 p-4 md:p-6 rounded-lg border border-gray-700">
                        <p class="text-gray-400 text-xs md:text-sm">Equity</p>
                        <p class="text-xl md:text-2xl font-bold text-green-400">${{ account.equity }}</p>
                    </div>
                    <div class="bg-gray-800 p-4 md:p-6 rounded-lg border border-gray-700">
                        <p class="text-gray-400 text-xs md:text-sm">Margin Level</p>
                        <p class="text-xl md:text-2xl font-bold" :class="account.margin_level < 1000 ? 'text-red-400' : 'text-blue-400'">{{ account.margin_level }}%</p>
                    </div>
                    <div class="bg-gray-800 p-4 md:p-6 rounded-lg border border-gray-700">
                        <p class="text-gray-400 text-xs md:text-sm">Status</p>
                        <p class="text-xl md:text-2xl font-bold text-brand">{{ account.status }}</p>
                    </div>
                    <div class="bg-gray-800 p-4 md:p-6 rounded-lg border border-gray-700">
                        <p class="text-gray-400 text-xs md:text-sm">Active Positions</p>
                        <p class="text-xl md:text-2xl font-bold">{{ account.active_positions }}</p>
                    </div>
                </div>
            </div>

            <!-- News Tab -->
            <div v-if="currentTab === 'news'">
                <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-4 md:mb-6 gap-4">
                    <h2 class="text-xl md:text-2xl font-bold">News Intelligence</h2>
                    <button @click="triggerScan" class="bg-brand hover:bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium w-full sm:w-auto">Scan Now</button>
                </div>
                <div class="bg-gray-800 p-4 md:p-6 rounded-lg border border-gray-700 mb-4 md:mb-6">
                    <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-4 gap-4">
                        <div>
                            <p class="text-gray-400 text-xs md:text-sm">Geopolitical Risk Score</p>
                            <p class="text-3xl md:text-4xl font-bold" :class="news.risk_score > newsConfigForm.risk_threshold_high ? 'text-red-500' : (news.risk_score > newsConfigForm.risk_threshold_low ? 'text-yellow-500' : 'text-green-500')">{{ news.risk_score }}/100</p>
                            <p class="text-sm font-semibold mt-1" :class="news.risk_score > newsConfigForm.risk_threshold_high ? 'text-red-400' : (news.risk_score > newsConfigForm.risk_threshold_low ? 'text-yellow-400' : 'text-green-400')">{{ news.bias }}</p>
                        </div>
                        <div class="text-right w-full sm:w-auto">
                            <p class="text-gray-400 text-xs md:text-sm">Primary Driver</p>
                            <p class="text-lg md:text-xl font-bold text-white">{{ news.primary_driver }}</p>
                        </div>
                    </div>
                    <div class="mt-4 p-3 md:p-4 bg-gray-900 rounded border-l-4 border-brand">
                        <p class="text-xs md:text-sm text-gray-300 font-mono">{{ news.recommendation }}</p>
                    </div>
                </div>
                <h3 class="text-lg font-bold mb-4">Verified Sources</h3>
                <div class="space-y-4">
                    <div v-for="src in news.verified_sources" :key="src.source_url" class="bg-gray-800 p-4 rounded-lg border border-gray-700 flex flex-col sm:flex-row justify-between items-start gap-4">
                        <div class="flex-1">
                            <a :href="src.source_url" target="_blank" class="text-brand hover:underline font-medium text-sm md:text-base">{{ src.headline }}</a>
                            <p class="text-xs text-gray-500 mt-1">{{ src.publisher }} • {{ src.publish_timestamp }}</p>
                            <div class="flex flex-wrap gap-2 mt-2">
                                <span v-for="kw in src.matched_keywords" class="px-2 py-0.5 bg-gray-700 text-xs rounded text-gray-300">{{ kw }}</span>
                            </div>
                        </div>
                        <div class="text-right w-full sm:w-auto flex sm:flex-col justify-between sm:justify-end items-center sm:items-end">
                            <span class="text-xs px-2 py-1 rounded bg-green-900 text-green-300 border border-green-700">Verified</span>
                            <p class="text-xs mt-1 sm:mt-2" :class="src.individual_sentiment_score < 0 ? 'text-red-400' : 'text-green-400'">Score: {{ src.individual_sentiment_score }}</p>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Settings Tab -->
            <div v-if="currentTab === 'settings'">
                <h2 class="text-xl md:text-2xl font-bold mb-4 md:mb-6">EA Configuration</h2>
                <form @submit.prevent="saveConfig" class="bg-gray-800 p-4 md:p-6 rounded-lg border border-gray-700 max-w-lg space-y-4 mb-8">
                    <div>
                        <label class="block text-sm font-medium text-gray-400 mb-1">Base Lot Size</label>
                        <input v-model.number="configForm.base_lot_size" type="number" step="0.01" class="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-400 mb-1">Grid Distance (Points)</label>
                        <input v-model.number="configForm.grid_distance_points" type="number" class="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-400 mb-1">Max Total Exposure (Lots)</label>
                        <input v-model.number="configForm.max_total_exposure_lots" type="number" step="0.01" class="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white">
                    </div>
                    <button type="submit" class="w-full bg-brand hover:bg-blue-600 text-white py-2 rounded-md font-medium">Update EA Parameters</button>
                </form>

                <h2 class="text-xl md:text-2xl font-bold mb-4 md:mb-6">News Intelligence Configuration</h2>
                <form @submit.prevent="saveNewsConfig" class="bg-gray-800 p-4 md:p-6 rounded-lg border border-gray-700 max-w-lg space-y-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-400 mb-1">Keywords (comma-separated)</label>
                        <input v-model="newsConfigForm.keywords" type="text" class="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white">
                        <p class="text-xs text-gray-500 mt-1">Words that trigger risk analysis (e.g., Tariff, Fed, War).</p>
                    </div>
                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                            <label class="block text-sm font-medium text-gray-400 mb-1">Low Risk Threshold (0-100)</label>
                            <input v-model.number="newsConfigForm.risk_threshold_low" type="number" class="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white">
                            <p class="text-xs text-gray-500 mt-1">Score below this = Bullish Bias</p>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-400 mb-1">High Risk Threshold (0-100)</label>
                            <input v-model.number="newsConfigForm.risk_threshold_high" type="number" class="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white">
                            <p class="text-xs text-gray-500 mt-1">Score above this = Bearish Bias</p>
                        </div>
                    </div>
                    <button type="submit" class="w-full bg-brand hover:bg-blue-600 text-white py-2 rounded-md font-medium">Update News Parameters</button>
                </form>
            </div>
        </main>
    </div>
    <script src="/static/app.js"></script>
</body>
</html>"""

with open('web-ui/index.html', 'w') as f:
    f.write(index_html)

print("✅ Mobile-responsive UI files updated successfully!")
