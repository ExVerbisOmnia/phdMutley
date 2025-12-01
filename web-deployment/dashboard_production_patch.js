/**
 * ============================================================================
 * DASHBOARD.HTML - PRODUCTION PATCH FILE
 * ============================================================================
 * 
 * This file contains the JavaScript code blocks that need to be REPLACED
 * in dashboard.html (to be renamed index.html) for production deployment.
 * 
 * INSTRUCTIONS FOR CLAUDE CODE:
 * 1. Copy dashboard.html to frontend/index.html
 * 2. Find the CONFIGURATION section (around line 758-771)
 * 3. Replace the API_BASE constant with the new block below
 * 4. After Railway deployment, update the production URL
 * 
 * ============================================================================
 */

// =============================================================================
// CHANGE 1: REPLACE API CONFIGURATION (lines 758-771)
// =============================================================================

// FIND THIS:
/*
        // ================================================================
        // CONFIGURATION
        // ================================================================

        // API base URL - adjust for your deployment
        const API_BASE = 'http://127.0.0.1:5000/api';

        // Color mapping for regions
        const REGION_COLORS = {
            'Global North': '#3498db',
            'Global South': '#e74c3c',
            'International': '#9b59b6',
            'Unknown': '#95a5a6'
        };
*/

// REPLACE WITH:
/*
        // ================================================================
        // CONFIGURATION
        // ================================================================

        // ================================================================
        // API URL DETECTION - Auto-detect environment
        // ================================================================
        
        /**
         * Determine API base URL based on current environment
         * - Production (Railway): Use the Railway API service URL
         * - Development: Use localhost:5000
         * 
         * IMPORTANT: After deploying to Railway, update the production URL below!
         */
        const API_BASE = (() => {
            const hostname = window.location.hostname;
            
            // ================================================
            // PRODUCTION: Railway deployment
            // ================================================
            // TODO: Replace this URL with your actual Railway API URL after deployment
            // Example: 'https://climate-litigation-api-production.up.railway.app/api'
            const RAILWAY_API_URL = 'https://YOUR-API-SERVICE.up.railway.app/api';
            
            // If we're on a Railway domain
            if (hostname.includes('railway.app')) {
                console.log('🚀 Production mode: Using Railway API');
                return RAILWAY_API_URL;
            }
            
            // If we're on a custom domain (not localhost)
            if (hostname !== 'localhost' && 
                hostname !== '127.0.0.1' && 
                !hostname.startsWith('192.168.') &&
                !hostname.startsWith('10.')) {
                // Assume API is at same domain with /api path
                console.log('🌐 Custom domain mode: Using same-origin API');
                return `${window.location.origin}/api`;
            }
            
            // ================================================
            // DEVELOPMENT: Local server
            // ================================================
            console.log('🔧 Development mode: Using localhost API');
            return 'http://127.0.0.1:5000/api';
        })();
        
        console.log('📡 API Base URL:', API_BASE);

        // Color mapping for regions
        const REGION_COLORS = {
            'Global North': '#3498db',
            'Global South': '#e74c3c',
            'International': '#9b59b6',
            'Unknown': '#95a5a6'
        };
*/

// =============================================================================
// ADDITIONAL IMPROVEMENT: BETTER ERROR HANDLING FOR API STATUS
// =============================================================================

// FIND THE checkApiHealth FUNCTION (around line 810) AND OPTIONALLY ENHANCE:
/*
        async function checkApiHealth() {
            const statusEl = document.getElementById('api-status');
            const textEl = document.getElementById('api-status-text');

            try {
                const data = await apiRequest('/health');
                statusEl.className = 'status-indicator connected';
                textEl.textContent = `Connected to API (v${data.version || '1.0'})`;
                return true;
            } catch (error) {
                statusEl.className = 'status-indicator disconnected';
                textEl.textContent = 'API Disconnected - Check server';
                return false;
            }
        }
*/

// REPLACE WITH (optional enhancement):
/*
        /**
         * Check API health and update status indicator
         * Enhanced with better error messages for production debugging
         */
        async function checkApiHealth() {
            const statusEl = document.getElementById('api-status');
            const textEl = document.getElementById('api-status-text');

            try {
                const data = await apiRequest('/health');
                statusEl.className = 'status-indicator connected';
                
                // Show environment info
                const env = API_BASE.includes('railway.app') ? '☁️ Railway' : '💻 Local';
                textEl.textContent = `${env} Connected (v${data.version || '1.0'})`;
                
                console.log('✅ API Health Check Passed:', data);
                return true;
            } catch (error) {
                statusEl.className = 'status-indicator disconnected';
                
                // Provide helpful error message
                if (API_BASE.includes('YOUR-API-SERVICE')) {
                    textEl.textContent = '⚠️ Update API URL in code!';
                    console.error('❌ API URL not configured! Update RAILWAY_API_URL constant.');
                } else {
                    textEl.textContent = '❌ API Disconnected';
                    console.error('❌ API Health Check Failed:', error);
                    console.log('Attempted URL:', API_BASE + '/health');
                }
                return false;
            }
        }
*/

// =============================================================================
// COMPLETE REPLACEMENT BLOCK (for convenience)
// =============================================================================
// Copy everything between the SCRIPT_START and SCRIPT_END markers
// to replace lines 757-825 in dashboard.html

const COMPLETE_REPLACEMENT_BLOCK = `
    <script>
        // ================================================================
        // CONFIGURATION
        // ================================================================

        /**
         * API URL Detection - Auto-detect environment
         * - Production (Railway): Use the Railway API service URL
         * - Development: Use localhost:5000
         * 
         * IMPORTANT: After deploying to Railway, update RAILWAY_API_URL below!
         */
        const API_BASE = (() => {
            const hostname = window.location.hostname;
            
            // ------------------------------------------------
            // PRODUCTION: Railway deployment
            // ------------------------------------------------
            // TODO: Update this URL after Railway deployment!
            const RAILWAY_API_URL = 'https://YOUR-API-SERVICE.up.railway.app/api';
            
            if (hostname.includes('railway.app')) {
                console.log('🚀 Production mode: Railway API');
                return RAILWAY_API_URL;
            }
            
            if (hostname !== 'localhost' && 
                hostname !== '127.0.0.1' && 
                !hostname.startsWith('192.168.') &&
                !hostname.startsWith('10.')) {
                console.log('🌐 Custom domain: same-origin API');
                return \`\${window.location.origin}/api\`;
            }
            
            // ------------------------------------------------
            // DEVELOPMENT: Local server
            // ------------------------------------------------
            console.log('🔧 Development mode: localhost API');
            return 'http://127.0.0.1:5000/api';
        })();
        
        console.log('📡 API Base URL:', API_BASE);

        // Color mapping for regions
        const REGION_COLORS = {
            'Global North': '#3498db',
            'Global South': '#e74c3c',
            'International': '#9b59b6',
            'Unknown': '#95a5a6'
        };

        // ================================================================
        // API FUNCTIONS
        // ================================================================

        /**
         * Make an API request with error handling
         * @param {string} endpoint - API endpoint path
         * @param {object} params - Query parameters
         * @returns {Promise<object>} - Response data
         */
        async function apiRequest(endpoint, params = {}) {
            const url = new URL(\`\${API_BASE}\${endpoint}\`);
            Object.keys(params).forEach(key => {
                if (params[key] !== null && params[key] !== '') {
                    url.searchParams.append(key, params[key]);
                }
            });

            try {
                const response = await fetch(url);
                const json = await response.json();

                if (json.status === 'success') {
                    return json.data;
                } else {
                    throw new Error(json.message || 'API error');
                }
            } catch (error) {
                console.error(\`API Error (\${endpoint}):\`, error);
                throw error;
            }
        }

        /**
         * Check API health and update status indicator
         */
        async function checkApiHealth() {
            const statusEl = document.getElementById('api-status');
            const textEl = document.getElementById('api-status-text');

            try {
                const data = await apiRequest('/health');
                statusEl.className = 'status-indicator connected';
                
                const env = API_BASE.includes('railway.app') ? '☁️' : '💻';
                textEl.textContent = \`\${env} Connected (v\${data.version || '1.0'})\`;
                console.log('✅ API Connected:', data);
                return true;
            } catch (error) {
                statusEl.className = 'status-indicator disconnected';
                
                if (API_BASE.includes('YOUR-API-SERVICE')) {
                    textEl.textContent = '⚠️ Update API URL!';
                    console.error('❌ Configure RAILWAY_API_URL in code!');
                } else {
                    textEl.textContent = '❌ API Disconnected';
                    console.error('❌ Connection failed:', error);
                }
                return false;
            }
        }
`;

// =============================================================================
// END OF PATCH FILE
// =============================================================================
