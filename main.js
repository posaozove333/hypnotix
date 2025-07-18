import Hls from 'hls.js';

class HypnotixApp {
    constructor() {
        this.providers = this.loadProviders();
        this.favorites = this.loadFavorites();
        this.currentProvider = null;
        this.currentChannel = null;
        this.channels = [];
        this.filteredChannels = [];
        this.hls = null;
        
        this.initializeElements();
        this.bindEvents();
        this.loadProvidersIntoSelect();
        this.updateStatus('Ready');
    }

    initializeElements() {
        // Header elements
        this.backBtn = document.getElementById('backBtn');
        this.searchBtn = document.getElementById('searchBtn');
        this.menuBtn = document.getElementById('menuBtn');
        
        // Sidebar elements
        this.providerSelect = document.getElementById('providerSelect');
        this.addProviderBtn = document.getElementById('addProviderBtn');
        this.searchSection = document.getElementById('searchSection');
        this.searchInput = document.getElementById('searchInput');
        this.categoriesList = document.getElementById('categoriesList');
        
        // Content elements
        this.channelsTitle = document.getElementById('channelsTitle');
        this.channelsCount = document.getElementById('channelsCount');
        this.channelsList = document.getElementById('channelsList');
        
        // Player elements
        this.videoPlayer = document.getElementById('videoPlayer');
        this.videoOverlay = document.getElementById('videoOverlay');
        this.playBtn = document.getElementById('playBtn');
        this.stopBtn = document.getElementById('stopBtn');
        this.fullscreenBtn = document.getElementById('fullscreenBtn');
        this.currentlyPlaying = document.getElementById('currentlyPlaying');
        
        // Modal elements
        this.addProviderModal = document.getElementById('addProviderModal');
        this.closeModal = document.getElementById('closeModal');
        this.providerName = document.getElementById('providerName');
        this.providerType = document.getElementById('providerType');
        this.providerUrl = document.getElementById('providerUrl');
        this.providerFile = document.getElementById('providerFile');
        this.fileGroup = document.getElementById('fileGroup');
        this.cancelProvider = document.getElementById('cancelProvider');
        this.saveProvider = document.getElementById('saveProvider');
        
        // Status
        this.statusText = document.getElementById('statusText');
    }

    bindEvents() {
        // Header events
        this.searchBtn.addEventListener('click', () => this.toggleSearch());
        this.addProviderBtn.addEventListener('click', () => this.showAddProviderModal());
        
        // Provider events
        this.providerSelect.addEventListener('change', (e) => this.selectProvider(e.target.value));
        
        // Search events
        this.searchInput.addEventListener('input', (e) => this.searchChannels(e.target.value));
        
        // Player events
        this.playBtn.addEventListener('click', () => this.togglePlayback());
        this.stopBtn.addEventListener('click', () => this.stopPlayback());
        this.fullscreenBtn.addEventListener('click', () => this.toggleFullscreen());
        
        // Modal events
        this.closeModal.addEventListener('click', () => this.hideAddProviderModal());
        this.cancelProvider.addEventListener('click', () => this.hideAddProviderModal());
        this.saveProvider.addEventListener('click', () => this.saveNewProvider());
        this.providerType.addEventListener('change', (e) => this.toggleProviderInputs(e.target.value));
        
        // Keyboard events
        document.addEventListener('keydown', (e) => this.handleKeyboard(e));
        
        // Click outside modal to close
        this.addProviderModal.addEventListener('click', (e) => {
            if (e.target === this.addProviderModal) {
                this.hideAddProviderModal();
            }
        });
    }

    loadProviders() {
        const saved = localStorage.getItem('hypnotix-providers');
        if (saved) {
            return JSON.parse(saved);
        }
        
        // Default provider
        return [{
            name: 'Free-TV',
            type: 'm3u',
            url: 'https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8'
        }];
    }

    saveProviders() {
        localStorage.setItem('hypnotix-providers', JSON.stringify(this.providers));
    }

    loadFavorites() {
        const saved = localStorage.getItem('hypnotix-favorites');
        return saved ? JSON.parse(saved) : [];
    }

    saveFavorites() {
        localStorage.setItem('hypnotix-favorites', JSON.stringify(this.favorites));
    }

    loadProvidersIntoSelect() {
        this.providerSelect.innerHTML = '<option value="">Select Provider</option>';
        this.providers.forEach((provider, index) => {
            const option = document.createElement('option');
            option.value = index;
            option.textContent = provider.name;
            this.providerSelect.appendChild(option);
        });
    }

    async selectProvider(index) {
        if (!index) {
            this.currentProvider = null;
            this.updateChannelsList([]);
            return;
        }

        this.currentProvider = this.providers[index];
        this.updateStatus(`Loading ${this.currentProvider.name}...`);
        
        try {
            await this.loadChannelsFromProvider(this.currentProvider);
            this.updateCategories();
            this.updateChannelsList(this.channels);
            this.updateStatus(`Loaded ${this.channels.length} channels`);
        } catch (error) {
            console.error('Error loading provider:', error);
            this.updateStatus(`Failed to load ${this.currentProvider.name}`);
        }
    }

    async loadChannelsFromProvider(provider) {
        if (provider.type === 'local') {
            // Handle local file (would need file input)
            throw new Error('Local files not supported in web version');
        }

        const response = await fetch(provider.url);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const m3uContent = await response.text();
        this.channels = this.parseM3U(m3uContent);
        this.filteredChannels = [...this.channels];
    }

    parseM3U(content) {
        const lines = content.split('\n').map(line => line.trim());
        const channels = [];
        let currentChannel = null;

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            
            if (line.startsWith('#EXTINF:')) {
                currentChannel = this.parseExtinf(line);
            } else if (line && !line.startsWith('#') && currentChannel) {
                currentChannel.url = line;
                currentChannel.id = channels.length;
                channels.push(currentChannel);
                currentChannel = null;
            }
        }

        return channels;
    }

    parseExtinf(line) {
        const channel = {
            name: '',
            group: '',
            logo: '',
            url: ''
        };

        // Extract parameters
        const paramRegex = /(\w+(?:-\w+)*)="([^"]*)"/g;
        let match;
        
        while ((match = paramRegex.exec(line)) !== null) {
            const [, key, value] = match;
            switch (key) {
                case 'tvg-name':
                    channel.name = value;
                    break;
                case 'group-title':
                    channel.group = value;
                    break;
                case 'tvg-logo':
                    channel.logo = value;
                    break;
            }
        }

        // Extract title (after the last comma)
        const titleMatch = line.match(/,(.+)$/);
        if (titleMatch && !channel.name) {
            channel.name = titleMatch[1].trim();
        }

        return channel;
    }

    updateCategories() {
        const categories = new Set();
        this.channels.forEach(channel => {
            if (channel.group) {
                categories.add(channel.group);
            }
        });

        // Clear existing categories (except favorites)
        const existingCategories = this.categoriesList.querySelectorAll('.category-item:not([data-type="favorites"])');
        existingCategories.forEach(cat => cat.remove());

        // Add TV Channels category
        if (this.channels.length > 0) {
            this.addCategory('All Channels', 'all', this.channels.length);
        }

        // Add group categories
        Array.from(categories).sort().forEach(group => {
            const count = this.channels.filter(ch => ch.group === group).length;
            this.addCategory(group, 'group', count, group);
        });
    }

    addCategory(name, type, count, data = null) {
        const item = document.createElement('div');
        item.className = 'category-item';
        item.dataset.type = type;
        if (data) item.dataset.group = data;
        
        item.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/>
                <line x1="8" y1="21" x2="16" y2="21"/>
                <line x1="12" y1="17" x2="12" y2="21"/>
            </svg>
            ${name} ${count ? `(${count})` : ''}
        `;
        
        item.addEventListener('click', () => this.selectCategory(item));
        this.categoriesList.appendChild(item);
    }

    selectCategory(categoryElement) {
        // Remove active class from all categories
        this.categoriesList.querySelectorAll('.category-item').forEach(item => {
            item.classList.remove('active');
        });
        
        // Add active class to selected category
        categoryElement.classList.add('active');
        
        const type = categoryElement.dataset.type;
        let channelsToShow = [];
        let title = '';

        switch (type) {
            case 'favorites':
                channelsToShow = this.channels.filter(ch => this.favorites.includes(ch.name));
                title = 'Favorites';
                break;
            case 'all':
                channelsToShow = this.channels;
                title = 'All Channels';
                break;
            case 'group':
                const group = categoryElement.dataset.group;
                channelsToShow = this.channels.filter(ch => ch.group === group);
                title = group;
                break;
        }

        this.filteredChannels = channelsToShow;
        this.updateChannelsList(channelsToShow);
        this.channelsTitle.textContent = title;
    }

    updateChannelsList(channels) {
        this.channelsList.innerHTML = '';
        
        if (channels.length === 0) {
            this.channelsList.innerHTML = `
                <div class="no-content">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
                        <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/>
                        <line x1="8" y1="21" x2="16" y2="21"/>
                        <line x1="12" y1="17" x2="12" y2="21"/>
                    </svg>
                    <p>No channels found</p>
                </div>
            `;
            this.channelsCount.textContent = '';
            return;
        }

        this.channelsCount.textContent = `${channels.length} channels`;

        channels.forEach(channel => {
            const item = document.createElement('div');
            item.className = 'channel-item';
            item.dataset.channelId = channel.id;
            
            const isFavorite = this.favorites.includes(channel.name);
            
            item.innerHTML = `
                <div class="channel-info">
                    <div class="channel-name">${channel.name}</div>
                    ${channel.group ? `<div class="channel-group">${channel.group}</div>` : ''}
                </div>
                <div class="channel-actions">
                    <button class="favorite-btn ${isFavorite ? 'active' : ''}" data-channel="${channel.name}">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="${isFavorite ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2">
                            <polygon points="12,2 15.09,8.26 22,9.27 17,14.14 18.18,21.02 12,17.77 5.82,21.02 7,14.14 2,9.27 8.91,8.26"/>
                        </svg>
                    </button>
                </div>
            `;
            
            item.addEventListener('click', (e) => {
                if (!e.target.closest('.favorite-btn')) {
                    this.selectChannel(channel);
                }
            });
            
            const favoriteBtn = item.querySelector('.favorite-btn');
            favoriteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleFavorite(channel.name);
            });
            
            this.channelsList.appendChild(item);
        });
    }

    selectChannel(channel) {
        // Remove active class from all channels
        this.channelsList.querySelectorAll('.channel-item').forEach(item => {
            item.classList.remove('active');
        });
        
        // Add active class to selected channel
        const channelElement = this.channelsList.querySelector(`[data-channel-id="${channel.id}"]`);
        if (channelElement) {
            channelElement.classList.add('active');
        }
        
        this.currentChannel = channel;
        this.playChannel(channel);
    }

    async playChannel(channel) {
        this.updateStatus(`Loading ${channel.name}...`);
        this.currentlyPlaying.textContent = `Loading: ${channel.name}`;
        
        try {
            // Stop any existing playback
            this.stopPlayback();
            
            // Hide overlay
            this.videoOverlay.classList.add('hidden');
            
            // Check if HLS is supported
            if (Hls.isSupported() && (channel.url.includes('.m3u8') || channel.url.includes('m3u'))) {
                this.hls = new Hls({
                    enableWorker: false,
                    lowLatencyMode: true,
                    backBufferLength: 90
                });
                
                this.hls.loadSource(channel.url);
                this.hls.attachMedia(this.videoPlayer);
                
                this.hls.on(Hls.Events.MANIFEST_PARSED, () => {
                    this.videoPlayer.play();
                    this.currentlyPlaying.textContent = `Playing: ${channel.name}`;
                    this.updateStatus(`Playing ${channel.name}`);
                    this.playBtn.innerHTML = `
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <rect x="6" y="4" width="4" height="16"/>
                            <rect x="14" y="4" width="4" height="16"/>
                        </svg>
                    `;
                    this.playBtn.disabled = false;
                    this.stopBtn.disabled = false;
                });
                
                this.hls.on(Hls.Events.ERROR, (event, data) => {
                    console.error('HLS Error:', data);
                    this.fallbackToDirectPlay(channel);
                });
                
            } else if (this.videoPlayer.canPlayType('application/vnd.apple.mpegurl')) {
                // Safari native HLS support
                this.videoPlayer.src = channel.url;
                await this.videoPlayer.play();
                this.currentlyPlaying.textContent = `Playing: ${channel.name}`;
                this.updateStatus(`Playing ${channel.name}`);
                this.playBtn.disabled = false;
                this.stopBtn.disabled = false;
            } else {
                // Try direct playback
                this.fallbackToDirectPlay(channel);
            }
            
        } catch (error) {
            console.error('Playback error:', error);
            this.updateStatus(`Failed to play ${channel.name}`);
            this.currentlyPlaying.textContent = `Error: ${channel.name}`;
        }
    }

    fallbackToDirectPlay(channel) {
        this.videoPlayer.src = channel.url;
        this.videoPlayer.play().then(() => {
            this.currentlyPlaying.textContent = `Playing: ${channel.name}`;
            this.updateStatus(`Playing ${channel.name}`);
            this.playBtn.disabled = false;
            this.stopBtn.disabled = false;
        }).catch(error => {
            console.error('Direct play failed:', error);
            this.updateStatus(`Cannot play ${channel.name} - format not supported`);
            this.currentlyPlaying.textContent = `Error: ${channel.name}`;
            this.videoOverlay.classList.remove('hidden');
        });
    }

    togglePlayback() {
        if (this.videoPlayer.paused) {
            this.videoPlayer.play();
            this.playBtn.innerHTML = `
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="6" y="4" width="4" height="16"/>
                    <rect x="14" y="4" width="4" height="16"/>
                </svg>
            `;
        } else {
            this.videoPlayer.pause();
            this.playBtn.innerHTML = `
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polygon points="5,3 19,12 5,21"/>
                </svg>
            `;
        }
    }

    stopPlayback() {
        if (this.hls) {
            this.hls.destroy();
            this.hls = null;
        }
        
        this.videoPlayer.pause();
        this.videoPlayer.src = '';
        this.videoOverlay.classList.remove('hidden');
        this.currentlyPlaying.textContent = 'No channel selected';
        this.updateStatus('Stopped');
        
        this.playBtn.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polygon points="5,3 19,12 5,21"/>
            </svg>
        `;
        this.playBtn.disabled = true;
        this.stopBtn.disabled = true;
    }

    toggleFullscreen() {
        if (!document.fullscreenElement) {
            this.videoPlayer.requestFullscreen().catch(err => {
                console.error('Error attempting to enable fullscreen:', err);
            });
        } else {
            document.exitFullscreen();
        }
    }

    toggleFavorite(channelName) {
        const index = this.favorites.indexOf(channelName);
        if (index > -1) {
            this.favorites.splice(index, 1);
        } else {
            this.favorites.push(channelName);
        }
        
        this.saveFavorites();
        
        // Update the favorite button
        const favoriteBtn = this.channelsList.querySelector(`[data-channel="${channelName}"]`);
        if (favoriteBtn) {
            const isActive = this.favorites.includes(channelName);
            favoriteBtn.classList.toggle('active', isActive);
            const svg = favoriteBtn.querySelector('svg');
            svg.setAttribute('fill', isActive ? 'currentColor' : 'none');
        }
    }

    toggleSearch() {
        const isVisible = this.searchSection.style.display !== 'none';
        this.searchSection.style.display = isVisible ? 'none' : 'block';
        
        if (!isVisible) {
            this.searchInput.focus();
        } else {
            this.searchInput.value = '';
            this.searchChannels('');
        }
    }

    searchChannels(query) {
        if (!query.trim()) {
            this.filteredChannels = [...this.channels];
        } else {
            const lowerQuery = query.toLowerCase();
            this.filteredChannels = this.channels.filter(channel =>
                channel.name.toLowerCase().includes(lowerQuery) ||
                (channel.group && channel.group.toLowerCase().includes(lowerQuery))
            );
        }
        
        this.updateChannelsList(this.filteredChannels);
        this.channelsTitle.textContent = query.trim() ? `Search: "${query}"` : 'All Channels';
    }

    showAddProviderModal() {
        this.addProviderModal.classList.add('show');
        this.providerName.focus();
    }

    hideAddProviderModal() {
        this.addProviderModal.classList.remove('show');
        this.clearProviderForm();
    }

    clearProviderForm() {
        this.providerName.value = '';
        this.providerUrl.value = '';
        this.providerFile.value = '';
        this.providerType.value = 'm3u';
        this.toggleProviderInputs('m3u');
    }

    toggleProviderInputs(type) {
        if (type === 'local') {
            this.fileGroup.style.display = 'block';
            this.providerUrl.parentElement.style.display = 'none';
        } else {
            this.fileGroup.style.display = 'none';
            this.providerUrl.parentElement.style.display = 'block';
        }
    }

    saveNewProvider() {
        const name = this.providerName.value.trim();
        const type = this.providerType.value;
        const url = this.providerUrl.value.trim();
        
        if (!name) {
            alert('Please enter a provider name');
            return;
        }
        
        if (type === 'm3u' && !url) {
            alert('Please enter a URL');
            return;
        }
        
        if (type === 'local' && !this.providerFile.files[0]) {
            alert('Please select a file');
            return;
        }
        
        const provider = {
            name,
            type,
            url: type === 'local' ? URL.createObjectURL(this.providerFile.files[0]) : url
        };
        
        this.providers.push(provider);
        this.saveProviders();
        this.loadProvidersIntoSelect();
        this.hideAddProviderModal();
        
        // Auto-select the new provider
        this.providerSelect.value = this.providers.length - 1;
        this.selectProvider(this.providers.length - 1);
    }

    handleKeyboard(e) {
        // Ctrl+F for search
        if (e.ctrlKey && e.key === 'f') {
            e.preventDefault();
            this.toggleSearch();
        }
        
        // F11 for fullscreen
        if (e.key === 'F11') {
            e.preventDefault();
            this.toggleFullscreen();
        }
        
        // Space for play/pause
        if (e.key === ' ' && !e.target.matches('input, textarea')) {
            e.preventDefault();
            if (!this.playBtn.disabled) {
                this.togglePlayback();
            }
        }
        
        // Escape to close modal or exit fullscreen
        if (e.key === 'Escape') {
            if (this.addProviderModal.classList.contains('show')) {
                this.hideAddProviderModal();
            } else if (document.fullscreenElement) {
                document.exitFullscreen();
            }
        }
    }

    updateStatus(message) {
        this.statusText.textContent = message;
    }
}

// Initialize the app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new HypnotixApp();
});