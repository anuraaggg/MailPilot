// src/components/Dashboard.jsx
import React, { useState, useEffect } from "react";
const API_URL = (import.meta.env.VITE_API_URL || '').trim();


const Dashboard = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [newKeyword, setNewKeyword] = useState("");
  const [showKeywordInput, setShowKeywordInput] = useState(false);
  const [captchaConfig, setCaptchaConfig] = useState(null);
  const [captchaResponse, setCaptchaResponse] = useState(null);
  const [showCaptcha, setShowCaptcha] = useState(false);
  const [captchaRendered, setCaptchaRendered] = useState(false);
  const [captchaError, setCaptchaError] = useState(null);

  // Check authentication status and fetch data
  useEffect(() => {
    // read query (?...) and hash (#...)
    const params = new URLSearchParams(window.location.search);
    const hashParams = new URLSearchParams(window.location.hash.slice(1));
    const authSuccess = params.get("auth_success") || hashParams.get("auth_success");

    console.log("Current URL:", window.location.href);
    console.log("auth_success param:", authSuccess);

    if (authSuccess === "true") {
      // strip both query and hash
      window.history.replaceState({}, document.title, window.location.pathname);
      setIsAuthenticated(true);

      setTimeout(() => {
        fetchDashboard();
        fetchCaptchaConfig();
      }, 1000);
    } else {
      const storedAuth = sessionStorage.getItem("mailpilot_authenticated");
      if (storedAuth === "true") {
        setIsAuthenticated(true);
        fetchDashboard();
        fetchCaptchaConfig();
      } else {
        setLoading(false);
        setIsAuthenticated(false);
        setError("Not signed in. Please log in first.");
      }
    }
  }, []);


  const fetchDashboard = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // First check if backend has our auth tokens
  const authStatusRes = await fetch(`${API_URL}/auth/status`);
      const authStatus = await authStatusRes.json();
      
      console.log("Auth status:", authStatus);
      
      if (!authStatus.authenticated) {
        setError("Authentication not found on server. Please log in again.");
        setIsAuthenticated(false);
        sessionStorage.removeItem("mailpilot_authenticated");
        return;
      }
      
  const res = await fetch(`${API_URL}/dashboard`);
      
      if (res.status === 401) {
        // Token expired or invalid, redirect to login
        sessionStorage.removeItem("mailpilot_authenticated");
        setIsAuthenticated(false);
        setError("Session expired. Please log in again.");
        return;
      }
      
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP ${res.status}: Failed to fetch dashboard data`);
      }
      
      const json = await res.json();
      setData(json);
      setIsAuthenticated(true);
      sessionStorage.setItem("mailpilot_authenticated", "true");
      
    } catch (err) {
      console.error("Dashboard fetch error:", err);
      setError(err.message);
      if (err.message.includes("401") || err.message.includes("Unauthorized")) {
        sessionStorage.removeItem("mailpilot_authenticated");
        setIsAuthenticated(false);
      }
    } finally {
      setLoading(false);
    }
  };

  const fetchCaptchaConfig = async () => {
    try {
      const res = await fetch(`${API_URL}/captcha/config`);
      if (!res.ok) {
        console.log("Captcha config endpoint not available:", res.status);
        setCaptchaConfig({ enabled: false, site_key: null });
        return;
      }
      
      const config = await res.json();
      console.log("Captcha config received:", config);
      setCaptchaConfig(config);
      
      // Set up global captcha callbacks
      if (config.enabled && config.site_key) {
        console.log("Setting up captcha callbacks with site key:", config.site_key);
        
        // Set up global callbacks
        window.onCaptchaSuccess = (token) => {
          console.log("Captcha success callback triggered, token:", token);
          setCaptchaResponse(token);
        };
        
        window.onCaptchaExpired = () => {
          console.log("Captcha expired callback triggered");
          setCaptchaResponse(null);
        };
        
        // Also set up error callback
        window.onCaptchaError = (error) => {
          console.log("Captcha error callback triggered:", error);
          setCaptchaResponse(null);
          setCaptchaError(`Captcha error: ${error}`);
        };
        
        // Check if reCAPTCHA script is loaded
        const checkRecaptchaLoaded = () => {
          if (typeof window.grecaptcha !== 'undefined') {
            console.log("reCAPTCHA script is loaded and ready");
            return true;
          }
          return false;
        };
        
        if (checkRecaptchaLoaded()) {
          console.log("reCAPTCHA already loaded");
        } else {
          console.log("reCAPTCHA not loaded, waiting for script...");
          // Wait for reCAPTCHA to load with more frequent checks
          const checkInterval = setInterval(() => {
            if (checkRecaptchaLoaded()) {
              console.log("reCAPTCHA loaded after waiting");
              clearInterval(checkInterval);
            }
          }, 500);
          
          // Clear interval after 15 seconds
          setTimeout(() => {
            clearInterval(checkInterval);
            if (!checkRecaptchaLoaded()) {
              console.error("reCAPTCHA failed to load after 15 seconds");
            }
          }, 15000);
        }
      } else {
        console.log("Captcha disabled or no site key - config:", config);
      }
    } catch (err) {
      console.error("Failed to fetch captcha config:", err);
      setCaptchaConfig({ enabled: false, site_key: null });
    }
  };

  // Auto-render captcha when modal opens
  useEffect(() => {
    if (showCaptcha && captchaConfig?.enabled && captchaConfig?.site_key && !captchaRendered) {
      console.log("Modal opened, attempting to render captcha...");
      console.log("Captcha config:", captchaConfig);
      console.log("reCAPTCHA available:", typeof window.grecaptcha !== 'undefined');
      
      const renderCaptcha = (attempt = 1) => {
        console.log(`Captcha render attempt ${attempt}`);
        
        // Check if reCAPTCHA is loaded
        if (typeof window.grecaptcha === 'undefined') {
          console.log("reCAPTCHA not loaded, waiting...");
          if (attempt < 30) { // Try for up to 15 seconds (30 * 500ms)
            setTimeout(() => renderCaptcha(attempt + 1), 500);
          } else {
            console.error("reCAPTCHA failed to load after 15 seconds");
          }
          return;
        }
        
        // Check if container exists
        const container = document.getElementById('recaptcha-container');
        if (!container) {
          console.log("Captcha container not found, waiting...");
          if (attempt < 30) {
            setTimeout(() => renderCaptcha(attempt + 1), 500);
          } else {
            console.error("Captcha container not found after 15 seconds");
          }
          return;
        }
        
        // Try to render captcha
        try {
          console.log("Attempting to render captcha with site key:", captchaConfig.site_key);
          
          // Clear any existing captcha
          if (container.hasChildNodes()) {
            container.innerHTML = '';
          }
          
          const widgetId = window.grecaptcha.render(container, {
            'sitekey': captchaConfig.site_key,
            'callback': 'onCaptchaSuccess',
            'expired-callback': 'onCaptchaExpired',
            'error-callback': 'onCaptchaError',
            'theme': 'dark',
            'size': 'normal'
          });
          
          setCaptchaRendered(true);
          console.log("Captcha rendered successfully with widget ID:", widgetId);
          
        } catch (error) {
          console.error("Error rendering captcha:", error);
          if (attempt < 5) {
            console.log(`Retrying captcha render in 1 second (attempt ${attempt + 1}/5)`);
            setTimeout(() => renderCaptcha(attempt + 1), 1000);
          } else {
            console.error("Failed to render captcha after 5 attempts");
          }
        }
      };
      
      // Wait a bit for the DOM to update, then start rendering
      setTimeout(() => renderCaptcha(1), 200);
    }
  }, [showCaptcha, captchaConfig, captchaRendered]);

  // Reset captcha rendered state when modal closes
  useEffect(() => {
    if (!showCaptcha) {
      setCaptchaRendered(false);
      setCaptchaResponse(null);
      setCaptchaError(null);
    }
  }, [showCaptcha]);

  // Function to reload reCAPTCHA script
  const reloadRecaptchaScript = () => {
    console.log("Attempting to reload reCAPTCHA script...");
    
    // Remove existing script if it exists
    const existingScript = document.querySelector('script[src*="recaptcha"]');
    if (existingScript) {
      existingScript.remove();
      console.log("Removed existing reCAPTCHA script");
    }
    
    // Create new script element
    const script = document.createElement('script');
    script.src = 'https://www.google.com/recaptcha/api.js?onload=onRecaptchaLoad&render=explicit';
    script.async = true;
    script.defer = true;
    
    // Set up global onload callback
    window.onRecaptchaLoad = () => {
      console.log("reCAPTCHA script reloaded successfully");
      setCaptchaError(null);
    };
    
    // Add error handling
    script.onerror = () => {
      console.error("Failed to load reCAPTCHA script");
      setCaptchaError("Failed to load reCAPTCHA script. Please check your internet connection.");
    };
    
    // Add script to document
    document.head.appendChild(script);
    console.log("Added new reCAPTCHA script to document");
  };

  const handleLogout = async () => {
    try {
  await fetch(`${API_URL}/logout`);
    } catch (err) {
      console.error("Logout error:", err);
    } finally {
      sessionStorage.removeItem("mailpilot_authenticated");
      setIsAuthenticated(false);
      setData(null);
      setError("Logged out successfully.");
    }
  };

  const handleLogin = async () => {
    try {
  const response = await fetch(`${API_URL}/login`);
      if (!response.ok) {
        throw new Error("Failed to get login URL");
      }
      const data = await response.json();
      if (data.auth_url) {
        window.location.href = data.auth_url;
      } else {
        throw new Error("No auth URL received");
      }
    } catch (error) {
      console.error("Login error:", error);
      setError("Failed to initiate login. Please try again.");
    }
  };

  const handleSyncEmails = async () => {
    try {
      console.log("Sync button clicked, captchaConfig:", captchaConfig, "captchaResponse:", captchaResponse);
      setLoading(true);
      
      // If captcha is enabled and configured, show captcha first
      if (captchaConfig?.enabled && captchaConfig?.site_key && !captchaResponse) {
        console.log("Showing captcha modal");
        setShowCaptcha(true);
        setLoading(false);
        return;
      }
      
      console.log("Proceeding with sync, requestBody:", captchaResponse ? { captcha_response: captchaResponse } : {});
      const requestBody = captchaResponse ? { captcha_response: captchaResponse } : {};
      
  const response = await fetch(`${API_URL}/sync-emails`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(requestBody)
      });
      
      console.log("Sync response status:", response.status);
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        console.log("Sync error response:", errorData);
        if (response.status === 429) {
          throw new Error("Too many sync attempts. Please wait before trying again.");
        } else if (response.status === 400 && errorData.detail?.includes("captcha")) {
          setShowCaptcha(true);
          setCaptchaResponse(null);
          setLoading(false);
          return;
        }
        throw new Error(errorData.detail || "Failed to sync emails");
      }
      
      const result = await response.json();
      console.log("Sync result:", result);
      
      // Reset captcha after successful sync
      setCaptchaResponse(null);
      setShowCaptcha(false);
      
      // Refresh dashboard data after sync
      await fetchDashboard();
      
    } catch (error) {
      console.error("Sync error:", error);
      setError(`Failed to sync emails: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleAddKeyword = async () => {
    if (!newKeyword.trim()) return;
    
    try {
  const response = await fetch(`${API_URL}/keywords`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ keyword: newKeyword.trim() })
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Failed to add keyword");
      }
      
      setNewKeyword("");
      setShowKeywordInput(false);
      await fetchDashboard(); // Refresh to show updated keywords
      
    } catch (error) {
      console.error("Add keyword error:", error);
      setError(`Failed to add keyword: ${error.message}`);
    }
  };

  const handleRemoveKeyword = async (keyword) => {
    try {
  const response = await fetch(`${API_URL}/keywords/${encodeURIComponent(keyword)}`, {
        method: "DELETE"
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Failed to remove keyword");
      }
      
      await fetchDashboard(); // Refresh to show updated keywords
      
    } catch (error) {
      console.error("Remove keyword error:", error);
      setError(`Failed to remove keyword: ${error.message}`);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-black px-4 py-8">
        <div className="flex flex-col items-center justify-center w-full max-w-xs" style={{paddingTop: '3rem', paddingBottom: '3rem'}}>
          <div className="relative mb-12 mt-8">
            <div className="w-24 h-24 flex items-center justify-center relative">
              <svg className="absolute animate-spin-slow" width="96" height="96" viewBox="0 0 96 96">
                <circle cx="48" cy="48" r="40" fill="none" stroke="#fff" strokeWidth="8" opacity="0.1" />
                <circle cx="48" cy="48" r="32" fill="none" stroke="#fff" strokeWidth="4" strokeDasharray="50 50" strokeLinecap="round" opacity="0.2" />
              </svg>
              <svg className="absolute animate-spin-reverse" width="64" height="64" viewBox="0 0 64 64">
                <circle cx="32" cy="32" r="24" fill="none" stroke="#fff" strokeWidth="4" strokeDasharray="30 30" strokeLinecap="round" opacity="0.15" />
              </svg>
              <span className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 block text-5xl font-extrabold text-blue-400 select-none" style={{fontFamily: 'Poppins, sans-serif', letterSpacing: '-0.05em'}}>M</span>
            </div>
          </div>
          <h1 className="text-5xl font-extrabold text-white mb-6 animate-pulse" style={{letterSpacing: '-0.03em'}}>MailPilot</h1>
          <p className="text-white/80 text-base mb-4 animate-fade-in" style={{marginTop: '-0.5rem'}}>The only Gmail companion app you will need</p>
          <p className="text-white text-lg mb-8 animate-fade-in">Loading your dashboard...</p>
          <div className="w-64 h-2 bg-white/10 rounded-full animate-gradient-x mb-2"></div>
          <style>{`
            .animate-spin-slow { animation: spin 2.5s linear infinite; }
            .animate-spin-reverse { animation: spin-reverse 3.5s linear infinite; }
            @keyframes spin { 100% { transform: rotate(360deg); } }
            @keyframes spin-reverse { 100% { transform: rotate(-360deg); } }
            .animate-fade-in { animation: fadeIn 1.2s ease-in; }
            @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
            .animate-gradient-x {
              background-size: 200% 100%;
              animation: gradient-x 2.5s linear infinite;
            }
            @keyframes gradient-x {
              0% { background-position: 0% 50%; }
              100% { background-position: 100% 50%; }
            }
          `}</style>
        </div>
      </div>
    );
  }

  if (error) {
    // If there's an error and user is not authenticated, show login screen
    if (!isAuthenticated) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-black">
          <div className="text-center max-w-md mx-auto p-8">
            <div className="mb-8">
              <h1 className="text-4xl font-extrabold text-white mb-2">MailPilot</h1>
              <p className="text-white/80 text-sm mb-6">The only Gmail companion app you will need</p>
            </div>
            <h2 className="text-2xl font-bold text-white mb-4">Authentication Required</h2>
            <p className="text-white/70 mb-6">{error}</p>
            <button
              onClick={handleLogin}
              className="group relative px-8 py-4 rounded-xl font-bold text-white transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-white focus:ring-offset-2 focus:ring-offset-black shadow-lg tracking-wide bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 hover:shadow-[0_0_20px_rgba(59,130,246,0.5)] hover:scale-105 active:scale-95"
            >
              <span className="relative z-10">Login with Google</span>
              <div className="absolute inset-0 bg-gradient-to-r from-blue-600 to-blue-700 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
            </button>
          </div>
        </div>
      );
    }
    
    // If there's an error but user is authenticated, show dashboard with error
    return (
      <div className="min-h-screen p-8 text-white bg-black">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-4xl font-extrabold text-white tracking-tight">
            <span className="inline-block align-middle font-extrabold text-blue-400" style={{fontFamily: 'Poppins, sans-serif', fontSize: '1.2em', letterSpacing: '-0.05em'}}>M</span>ailPilot Dashboard
          </h1>
          <button
            onClick={handleLogout}
            className="px-4 py-2 rounded-lg font-bold border-2 border-black transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-white focus:ring-offset-2 focus:ring-offset-black shadow-lg tracking-wide bg-white text-black hover:bg-black hover:text-white hover:border-white active:scale-95"
          >
            Logout
          </button>
        </div>
        <div className="bg-white/10 border border-white/20 rounded-lg p-4 mb-6">
          <p className="text-white/80">Error: {error}</p>
          <button
            onClick={fetchDashboard}
            className="mt-2 px-3 py-1 rounded-lg font-bold border-2 border-black transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-white focus:ring-offset-2 focus:ring-offset-black shadow-lg tracking-wide bg-white text-black hover:bg-black hover:text-white hover:border-white active:scale-95"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  // Font and button style helpers
  const fontFamily = 'Poppins, sans-serif';
  // Button style: visible on black, glassy, white border, white text, 3D, glow on hover
  const buttonBase = [
    'px-4', 'py-2', 'rounded-lg', 'border', 'border-white/30', 'bg-black/40', 'text-white',
    'backdrop-blur-sm', 'shadow', 'transition-all', 'duration-200', 'hover:border-white',
    'hover:shadow-[0_0_10px_rgba(255,255,255,0.6)]', 'hover:scale-105', 'focus:outline-none',
    'focus:ring-2', 'focus:ring-white', 'focus:ring-offset-2', 'focus:ring-offset-black',
    'font-medium', 'tracking-wide', 'select-none', 'active:scale-100', 'disabled:opacity-60', 'disabled:cursor-not-allowed'
  ].join(' ');

  // --- Keyword Alerts Widget (fixed scale) ---
  // Place this inside your return JSX where the widget is rendered
  {/* Keyword Alerts Widget */}
  <div className="lg:col-span-1">
    <div className="keyword-alerts-widget widget-container group relative p-6 rounded-2xl border border-white/20
          bg-gradient-to-br from-white/10 to-white/5 backdrop-blur-md
          shadow-[0_8px_32px_rgba(0,0,0,0.3)]
          hover:shadow-[0_20px_40px_rgba(255,255,255,0.1)]
          hover:border-white/40 hover:-translate-y-1
          transform transition-all duration-300 overflow-hidden will-change-transform">

      {/* 3D Background Elements */}
      <div className="absolute -top-6 -right-6 w-20 h-20 bg-white/5 rounded-full blur-xl group-hover:scale-150 transition-transform duration-700" />
      <div className="absolute -bottom-4 -left-4 w-16 h-16 bg-white/5 rounded-full blur-lg group-hover:scale-125 transition-transform duration-700" />

      <div className="flex justify-between items-center mb-4 z-10 relative">
        <h2 className="text-lg font-semibold text-white z-10">Keyword Alerts</h2>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowKeywordInput(!showKeywordInput)}
            className="w-20 min-w-[70px] px-3 py-1 rounded-lg border border-white/30 bg-white/10 text-white text-xs
                       hover:bg-white/20 hover:border-white/50 transition-all duration-200 z-10"
            style={{ minWidth: '70px' }}
          >
            {showKeywordInput ? "Cancel" : "Add"}
          </button>
          <span className="text-2xl opacity-80 ml-1">🏷️</span>
        </div>
      </div>

        {showKeywordInput && (
          <div className="mb-4 z-10 relative">
            <div className="flex gap-2 w-full">
              <input
                type="text"
                value={newKeyword}
                onChange={(e) => setNewKeyword(e.target.value)}
                placeholder="Enter keyword..."
                onKeyPress={(e) => e.key === 'Enter' && handleAddKeyword()}
                className="flex-grow bg-black/50 border border-white/30 rounded-lg px-3 py-2 text-white text-sm 
                           focus:outline-none focus:border-white/60 focus:bg-black/70 transition-all duration-200 min-w-0"
                style={{ width: 0 }}
              />
              <button
                onClick={handleAddKeyword}
                className="w-16 min-w-[60px] px-3 py-2 rounded-lg border border-blue-500/50 bg-blue-500/20 text-blue-200 text-sm 
                           hover:bg-blue-500/30 hover:border-blue-500/70 transition-all duration-200 flex-shrink-0"
                style={{ minWidth: '60px' }}
              >
                Add
              </button>
            </div>
          </div>
        )}

      <div className="space-y-2 z-10 relative max-h-48 overflow-y-auto scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
        {data.keywords?.length > 0 ? (
          data.keywords.map((kw, i) => (
            <div key={i} className="group/keyword flex justify-between items-center bg-white/5 p-3 rounded-xl border border-white/10
                                   hover:bg-white/10 hover:border-white/20 transition-all duration-300">
              <span className="text-white text-sm font-medium">{kw}</span>
               <button
                 onClick={() => handleRemoveKeyword(kw)}
                  className="px-2 py-1 rounded-lg border border-white/30 bg-white/10 text-white text-xs
                             hover:bg-white/20 hover:border-white/50 transition-all duration-200 opacity-100"
               >
                 Remove
               </button>
            </div>
          ))
        ) : (
          <div className="text-center py-6">
            <div className="text-3xl mb-2 opacity-30">🔍</div>
            <p className="text-gray-400 text-sm">No keywords set. Add keywords to filter important emails.</p>
          </div>
        )}
      </div>
    </div>
  </div>
  return (
  <div className="min-h-screen w-full text-white bg-black" style={{ fontFamily }}>
    <div className="w-full max-w-7xl mx-auto">
    <style>{`
      body, html, #root {
        font-family: 'Poppins', sans-serif !important;
        font-weight: 400;
        margin: 0;
        padding: 0;
        background: #000;
      }
      h1, h2, h3, h4, h5, h6 {
        font-family: 'Poppins', sans-serif !important;
        font-weight: 700;
      }
      .dashboard-heading { font-weight: 700; }
      .dashboard-subheading { font-weight: 600; }
      .dashboard-body { font-weight: 400; }
      
       /* Custom scrollbar styles to prevent glitching */
       .scrollbar-thin {
         scrollbar-width: thin;
         scrollbar-color: rgba(255, 255, 255, 0.15) transparent;
       }
       .scrollbar-thin::-webkit-scrollbar {
         width: 6px;
       }
       .scrollbar-thin::-webkit-scrollbar-track {
         background: transparent;
       }
       .scrollbar-thin::-webkit-scrollbar-thumb {
         background-color: rgba(255, 255, 255, 0.15);
         border-radius: 3px;
         transition: background-color 0.3s ease;
       }
       .scrollbar-thin::-webkit-scrollbar-thumb:hover {
         background-color: rgba(255, 255, 255, 0.25);
       }
       /* Prevent scrollbar glitch on widget hover */
       .widget-container:hover .scrollbar-thin::-webkit-scrollbar-thumb {
         background-color: rgba(255, 255, 255, 0.2);
       }
       /* Fix specific scrollbar glitch for Important Emails and Keyword Alerts */
       .widget-container .scrollbar-thin::-webkit-scrollbar-thumb {
         background-color: rgba(255, 255, 255, 0.15) !important;
         transition: background-color 0.2s ease !important;
       }
       .widget-container .scrollbar-thin::-webkit-scrollbar-thumb:hover {
         background-color: rgba(255, 255, 255, 0.25) !important;
       }
       /* Prevent hover conflicts */
       .widget-container:hover .scrollbar-thin::-webkit-scrollbar-thumb {
         background-color: rgba(255, 255, 255, 0.2) !important;
       }
       /* Specific fix for Important Emails and Keyword Alerts scrollbars */
       .important-emails-widget .scrollbar-thin::-webkit-scrollbar-thumb,
       .keyword-alerts-widget .scrollbar-thin::-webkit-scrollbar-thumb {
         background-color: rgba(255, 255, 255, 0.15) !important;
         transition: background-color 0.15s ease !important;
       }
       .important-emails-widget:hover .scrollbar-thin::-webkit-scrollbar-thumb,
       .keyword-alerts-widget:hover .scrollbar-thin::-webkit-scrollbar-thumb {
         background-color: rgba(255, 255, 255, 0.2) !important;
       }
     `}</style>
    <div className="relative mb-12 w-full max-w-7xl mx-auto px-2 sm:px-4 lg:px-8">
      {/* 3D Background Elements for Header */}
      <div className="absolute -top-20 -left-20 w-40 h-40 bg-white/5 rounded-full blur-3xl animate-pulse" />
      <div className="absolute -top-10 -right-10 w-32 h-32 bg-white/5 rounded-full blur-2xl animate-pulse" style={{ animationDelay: '1s' }} />
      <div className="flex justify-between items-center relative z-10">
        <div className="group">
          <h1 className="text-5xl dashboard-heading text-white tracking-tight drop-shadow-2xl group-hover:scale-105 transform transition-all duration-500">
            <span className="text-blue-400 font-extrabold">M</span>ailPilot Dashboard
          </h1>
          <div className="absolute -bottom-2 left-0 w-full h-1 bg-blue-500 rounded-full opacity-60 group-hover:opacity-100 transition-opacity duration-500" />
        </div>
        <div className="flex gap-4">
          <button
            onClick={handleSyncEmails}
            className="group relative px-6 py-3 rounded-xl border border-white/30 bg-white/10 text-white backdrop-blur-sm shadow-lg transition-all duration-300 hover:border-white/50 hover:bg-white/20 hover:shadow-[0_0_20px_rgba(255,255,255,0.3)] hover:scale-105 focus:outline-none focus:ring-2 focus:ring-white focus:ring-offset-2 focus:ring-offset-black font-medium tracking-wide disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={loading}
          >
            <span className="relative z-10">{loading ? "Syncing..." : "Sync Emails"}</span>
            <div className="absolute inset-0 bg-blue-500/10 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
          </button>
          <button
            onClick={handleLogout}
            className="group relative px-6 py-3 rounded-xl border border-white/30 bg-white/10 text-white backdrop-blur-sm shadow-lg transition-all duration-300 hover:border-white/50 hover:bg-white/20 hover:shadow-[0_0_20px_rgba(255,255,255,0.3)] hover:scale-105 focus:outline-none focus:ring-2 focus:ring-white focus:ring-offset-2 focus:ring-offset-black font-medium tracking-wide"
          >
            <span className="relative z-10">Logout</span>
            <div className="absolute inset-0 bg-white/10 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
          </button>
        </div>
      </div>
    </div>
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 w-full max-w-7xl mx-auto px-2 sm:px-4 lg:px-8">
      {/* Stats Row */}
     <div className="sm:col-span-1 lg:col-span-1 xl:col-span-1">
        {/* Unread Emails Widget */}
       <div className="widget-container group relative p-6 rounded-2xl border border-white/20 bg-gradient-to-br from-white/10 to-white/5 backdrop-blur-md shadow-[0_8px_32px_rgba(0,0,0,0.3)] hover:shadow-[0_20px_40px_rgba(255,255,255,0.1)] hover:border-white/40 hover:-translate-y-1 transform transition-all duration-300 overflow-hidden">
         {/* 3D Background Elements */}
         <div className="absolute -top-10 -right-10 w-20 h-20 bg-white/5 rounded-full blur-xl group-hover:scale-150 transition-transform duration-700" />
         <div className="absolute -bottom-5 -left-5 w-16 h-16 bg-blue-500/10 rounded-full blur-lg group-hover:scale-125 transition-transform duration-700" />
         
         {/* Floating Icons */}
         <div className="absolute top-4 right-4 text-2xl opacity-20 group-hover:opacity-40 transition-all duration-500">📧</div>
         
         <h2 className="text-lg font-semibold text-white mb-3 z-10 relative">Emails This Week</h2>
         <div className="relative">
            <div className="absolute inset-0 bg-blue-500/10 rounded-2xl blur-sm" />
           <div className="relative bg-black/30 rounded-2xl p-4 border border-white/10">
             <p className="text-4xl font-black text-white drop-shadow-2xl">
               {data.unreadEmails}
             </p>
             <div className="absolute bottom-0 left-0 w-full h-1 bg-blue-500 rounded-full opacity-60" />
           </div>
         </div>
       </div>
        </div>

{/* Important Emails Widget */}
<div className="sm:col-span-1 lg:col-span-2 xl:col-span-2">
  <div className="important-emails-widget widget-container group relative p-6 rounded-2xl border border-white/20 
                  bg-gradient-to-br from-white/10 to-white/5 backdrop-blur-md 
                  shadow-[0_8px_32px_rgba(0,0,0,0.3)] 
                  hover:shadow-[0_20px_40px_rgba(255,255,255,0.1)] 
                  hover:border-white/40 hover:-translate-y-1 
                  transform transition-all duration-300 overflow-hidden will-change-transform">

    {/* 3D Background Elements */}
     <div className="absolute -top-8 -left-8 w-24 h-24 bg-white/5 rounded-full blur-2xl group-hover:scale-150 transition-transform duration-700" />
     <div className="absolute -bottom-6 -right-6 w-20 h-20 bg-white/5 rounded-full blur-xl group-hover:scale-125 transition-transform duration-700" />

    {/* Floating Icon */}
    <div className="absolute top-4 right-4 text-2xl opacity-20 group-hover:opacity-40 transition-all duration-500">⭐</div>

    <h2 className="text-lg font-semibold text-white mb-2 z-10 relative">Important Emails</h2>
    <p className="text-xs text-gray-400 mb-4 z-10 relative">
      Based on your keywords: {data.keywords?.length > 0 ? data.keywords.join(', ') : 'None set'}
    </p>

    <div className="z-10 relative max-h-64 overflow-y-auto scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
      {data.importantEmails?.length > 0 ? (
        <div className="space-y-3">
          {data.importantEmails.map((email, i) => (
            <div key={i} className="group/email relative bg-white/5 p-4 rounded-xl border border-white/10 shadow-inner 
                                    hover:bg-white/10 hover:border-white/20 transition-all duration-300">
              {/* Glow effect */}
               <div className="absolute inset-0 bg-white/5 rounded-xl opacity-0 group-hover/email:opacity-100 transition-opacity duration-300" />
              <div className="relative z-10">
                <div className="flex justify-between items-start mb-2">
                  <span className="text-sm font-medium text-white">{email.from || "Unknown Sender"}</span>
                  <span className="text-xs text-gray-400">{email.date || "Unknown Date"}</span>
                </div>
                <p className="text-white text-sm font-medium mb-2 break-words">{email.subject || "No Subject"}</p>
                {email.summary && <p className="text-gray-400 text-xs italic">{email.summary}</p>}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-8">
          <div className="text-4xl mb-2 opacity-30">📭</div>
          <p className="text-gray-400 text-sm">No important emails found. Add keywords to filter emails.</p>
        </div>
      )}
    </div>
  </div>
</div>


{/* Keyword Alerts Widget */}
<div className="sm:col-span-1 lg:col-span-1 xl:col-span-1">
  <div className="keyword-alerts-widget widget-container group relative p-6 rounded-2xl border border-white/20 

            bg-gradient-to-br from-white/10 to-white/5 backdrop-blur-md 
            shadow-[0_8px_32px_rgba(0,0,0,0.3)] 
            hover:shadow-[0_20px_40px_rgba(255,255,255,0.1)] 
            hover:border-white/40 hover:-translate-y-1 
            transform transition-all duration-300 overflow-hidden will-change-transform">

  {/* 3D Background Elements */}
   <div className="absolute -top-6 -right-6 w-20 h-20 bg-white/5 rounded-full blur-xl group-hover:scale-150 transition-transform duration-700" />
   <div className="absolute -bottom-4 -left-4 w-16 h-16 bg-white/5 rounded-full blur-lg group-hover:scale-125 transition-transform duration-700" />

    <div className="flex justify-between items-center mb-4 z-10 relative">
      <h2 className="text-lg font-semibold text-white z-10">Keyword Alerts</h2>
      <div className="flex items-center gap-2">
        <button
          onClick={() => setShowKeywordInput(!showKeywordInput)}
          className="flex items-center justify-center px-3 h-9 min-w-[70px] rounded-lg border border-white/30 bg-white/10 text-white text-base font-medium hover:bg-white/20 hover:border-white/50 transition-all duration-200 z-10"
          style={{ boxSizing: 'border-box' }}
        >
          {showKeywordInput ? "Cancel" : "Add"}
        </button>
        <span className="text-2xl opacity-80 ml-1 flex items-center h-9">🏷️</span>
      </div>
    </div>

    {showKeywordInput && (
      <div className="mb-4 z-10 relative">
        <div className="flex gap-2 items-center">
          <input
            type="text"
            value={newKeyword}
            onChange={(e) => setNewKeyword(e.target.value)}
            placeholder="Enter keyword..."
            onKeyPress={(e) => e.key === 'Enter' && handleAddKeyword()}
            className="flex-1 bg-black/50 border border-white/30 rounded-lg px-3 h-9 text-white text-base focus:outline-none focus:border-white/60 focus:bg-black/70 transition-all duration-200"
            style={{ boxSizing: 'border-box' }}
          />
          <button
            onClick={handleAddKeyword}
            className="flex items-center justify-center px-3 h-9 min-w-[56px] rounded-lg border border-blue-500/50 bg-blue-500/20 text-blue-200 text-base font-medium hover:bg-blue-500/30 hover:border-blue-500/70 transition-all duration-200"
            style={{ boxSizing: 'border-box' }}
          >
            Add
          </button>
        </div>
      </div>
    )}

    <div className="space-y-2 z-10 relative max-h-48 overflow-y-auto scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
      {data.keywords?.length > 0 ? (
        data.keywords.map((kw, i) => (
          <div key={i} className="group/keyword flex justify-between items-center bg-white/5 p-3 rounded-xl border border-white/10 hover:bg-white/10 hover:border-white/20 transition-all duration-300">
            <span className="text-white text-base font-medium">{kw}</span>
            <button
              onClick={() => handleRemoveKeyword(kw)}
              className="flex items-center justify-center px-3 h-9 min-w-[70px] rounded-lg border border-red-500/50 bg-red-500/20 text-red-200 text-base font-medium hover:bg-red-500/30 hover:border-red-500/70 transition-all duration-200"
              style={{ boxSizing: 'border-box' }}
            >
              Remove
            </button>
          </div>
        ))
      ) : (
        <div className="text-center py-6">
          <div className="text-3xl mb-2 opacity-30">🔍</div>
          <p className="text-gray-400 text-sm">No keywords set. Add keywords to filter important emails.</p>
        </div>
      )}
    </div>
  </div>
</div>


     {/* Daily Summary: full width */}
     <div className="sm:col-span-2 lg:col-span-3 xl:col-span-4">
       <div className="widget-container group relative p-6 rounded-2xl border border-white/20 bg-gradient-to-br from-white/10 to-white/5 backdrop-blur-md shadow-[0_8px_32px_rgba(0,0,0,0.3)] hover:shadow-[0_20px_40px_rgba(255,255,255,0.1)] hover:border-white/40 hover:-translate-y-1 transform transition-all duration-300 overflow-hidden">
         {/* 3D Background Elements */}
          <div className="absolute -top-12 -left-12 w-32 h-32 bg-white/5 rounded-full blur-3xl group-hover:scale-150 transition-transform duration-700" />
          <div className="absolute -bottom-8 -right-8 w-24 h-24 bg-white/5 rounded-full blur-2xl group-hover:scale-125 transition-transform duration-700" />
         
         {/* Floating Icons */}
         <div className="absolute top-6 right-6 text-3xl opacity-20 group-hover:opacity-40 group-hover transition-all duration-500">📊</div>
         
         <h2 className="text-2xl font-bold text-white mb-4 z-10 relative">Daily Summary</h2>
         <div className="relative">
            <div className="absolute inset-0 bg-blue-500/10 rounded-2xl blur-sm" />
           <div className="relative bg-black/30 rounded-2xl p-6 border border-white/10">
             <p className="text-gray-300 text-lg leading-relaxed max-w-4xl">{data.dailySummary}</p>
             <div className="absolute bottom-0 left-0 w-full h-1 bg-blue-500 rounded-full opacity-60" />
           </div>
         </div>
       </div>
        </div>

     <div className="sm:col-span-2 lg:col-span-3 xl:col-span-4">
       <div className="widget-container group relative p-6 rounded-2xl border border-white/20 bg-gradient-to-br from-white/10 to-white/5 backdrop-blur-md shadow-[0_8px_32px_rgba(0,0,0,0.3)] hover:shadow-[0_20px_40px_rgba(255,255,255,0.1)] hover:border-white/40 hover:-translate-y-1 transform transition-all duration-300 overflow-hidden">
         {/* 3D Background Elements */}
          <div className="absolute -top-10 -left-10 w-28 h-28 bg-white/5 rounded-full blur-2xl group-hover:scale-150 transition-transform duration-700" />
          <div className="absolute -bottom-8 -right-8 w-24 h-24 bg-white/5 rounded-full blur-xl group-hover:scale-125 transition-transform duration-700" />
         
         {/* Floating Icons */}
         <div className="absolute top-4 right-4 text-2xl opacity-20 group-hover:opacity-40 group-hover transition-all duration-500">📬</div>
         
         <h2 className="text-lg font-semibold text-white mb-4 z-10 relative">Recent Emails</h2>
         <div className="z-10 relative max-h-80 overflow-y-auto scrollbar-thin">
          {data.recentEmails && data.recentEmails.length > 0 ? (
            <div className="space-y-3">
              {data.recentEmails.map((email, i) => (
                 <div key={i} className="group/email relative bg-white/5 p-4 rounded-xl border border-white/10 shadow-inner hover:bg-white/10 hover:border-white/20 transition-all duration-300">
                   {/* Email glow effect */}
                    <div className="absolute inset-0 bg-white/5 rounded-xl opacity-0 group-hover/email:opacity-100 transition-opacity duration-300" />
                   <div className="relative z-10">
                     <div className="flex justify-between items-start mb-2">
                       <span className="text-sm font-medium text-white">
                      {email.from || "Unknown Sender"}
                    </span>
                    <span className="text-xs text-gray-400">
                      {email.date || "Unknown Date"}
                    </span>
                  </div>
                     <p className="text-white text-sm font-medium break-words">
                    {email.subject || "No Subject"}
                  </p>
                   </div>
                </div>
              ))}
            </div>
          ) : (
             <div className="text-center py-12">
               <div className="text-5xl mb-4 opacity-30">📭</div>
               <p className="text-gray-400 text-lg">No recent emails found</p>
               <p className="text-gray-600 text-sm mt-2">
                This could be due to Gmail API permissions or no emails in your inbox
              </p>
            </div>
          )}
         </div>
       </div>
     </div>

      </div>

      {/* Captcha Modal */}
      {showCaptcha && captchaConfig?.enabled && (
        <div className="fixed inset-0 bg-black bg-opacity-80 flex items-center justify-center z-50">
          <div className="bg-white/10 p-8 rounded-lg max-w-md w-full mx-4 border border-white/20 text-center">
            <h3 className="text-xl font-semibold text-white mb-4">Verify You're Human</h3>
            <p className="text-white/80 mb-6">
              Please complete the captcha to sync your emails.
            </p>
            
            {/* Debug Information */}
            <div className="mb-4 p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg text-left">
              <p className="text-blue-200 text-xs font-semibold mb-2">Debug Information:</p>
              <div className="text-blue-200/80 text-xs space-y-1">
                <p>• Captcha Enabled: {captchaConfig?.enabled ? 'Yes' : 'No'}</p>
                <p>• Site Key: {captchaConfig?.site_key ? 'Present' : 'Missing'}</p>
                <p>• reCAPTCHA Script: {typeof window.grecaptcha !== 'undefined' ? 'Loaded' : 'Not Loaded'}</p>
                <p>• Container: {document.getElementById('recaptcha-container') ? 'Found' : 'Not Found'}</p>
                <p>• Rendered: {captchaRendered ? 'Yes' : 'No'}</p>
                <p>• Response: {captchaResponse ? 'Received' : 'None'}</p>
                {captchaError && <p>• Error: {captchaError}</p>}
              </div>
            </div>
            {captchaConfig.site_key ? (
              <div className="mb-6 flex justify-center">
                <div
                  id="recaptcha-container"
                  className="g-recaptcha"
                  data-sitekey={captchaConfig.site_key}
                  data-callback="onCaptchaSuccess"
                  data-expired-callback="onCaptchaExpired"
                ></div>
                {!captchaRendered && (
                  <div className="flex flex-col items-center gap-2">
                    <button
                      onClick={() => {
                        console.log("Manual captcha load button clicked");
                        const container = document.getElementById('recaptcha-container');
                        
                        if (typeof window.grecaptcha === 'undefined') {
                          console.log("reCAPTCHA not loaded, please wait for script to load");
                          alert("reCAPTCHA script is still loading. Please wait a moment and try again.");
                          return;
                        }
                        
                        if (!container) {
                          console.log("Captcha container not found");
                          alert("Captcha container not found. Please refresh the page.");
                          return;
                        }
                        
                        try {
                          console.log("Manually rendering captcha...");
                          
                          // Clear any existing captcha
                          if (container.hasChildNodes()) {
                            container.innerHTML = '';
                          }
                          
                          const widgetId = window.grecaptcha.render(container, {
                            'sitekey': captchaConfig.site_key,
                            'callback': 'onCaptchaSuccess',
                            'expired-callback': 'onCaptchaExpired',
                            'error-callback': 'onCaptchaError',
                            'theme': 'dark',
                            'size': 'normal'
                          });
                          
                          setCaptchaRendered(true);
                          console.log("Manual captcha render successful, widget ID:", widgetId);
                          
                        } catch (error) {
                          console.error("Manual captcha render failed:", error);
                          alert("Failed to load captcha. Please check the console for details.");
                        }
                      }}
                      className="px-4 py-2 rounded-lg font-bold border-2 border-white transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-white focus:ring-offset-2 focus:ring-offset-black shadow-lg tracking-wide bg-white text-black hover:bg-black hover:text-white hover:border-white active:scale-95 text-sm"
                    >
                      Load Captcha
                    </button>
                    <p className="text-white/60 text-xs">If captcha doesn't load automatically, click this button</p>
                    <div className="text-white/40 text-xs">
                      <p>Debug info:</p>
                      <p>reCAPTCHA loaded: {typeof window.grecaptcha !== 'undefined' ? 'Yes' : 'No'}</p>
                      <p>Container exists: {document.getElementById('recaptcha-container') ? 'Yes' : 'No'}</p>
                    </div>
                    <button
                      onClick={reloadRecaptchaScript}
                      className="px-3 py-1 rounded text-xs border border-yellow-500/50 bg-yellow-500/20 text-yellow-200 hover:bg-yellow-500/30 transition-all duration-200"
                    >
                      Reload reCAPTCHA Script
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <div className="mb-6 p-4 bg-yellow-500/20 border border-yellow-500/50 rounded-lg">
                <p className="text-yellow-200 text-sm">
                  Captcha is not properly configured. Please contact support or try again later.
                </p>
              </div>
            )}
            <div className="flex gap-3 justify-center">
              <button
                onClick={() => {
                  setShowCaptcha(false);
                  setCaptchaResponse(null);
                }}
                className={buttonBase}
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  if (captchaResponse) {
                    setShowCaptcha(false);
                    handleSyncEmails();
                  }
                }}
                disabled={!captchaResponse}
                className={buttonBase + (!captchaResponse ? ' opacity-50 cursor-not-allowed' : '')}
              >
                Continue Sync
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
    </div>
  );
};

export default Dashboard;
