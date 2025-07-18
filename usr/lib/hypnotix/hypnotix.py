#!/usr/bin/python3

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('XApp', '1.0')
from gi.repository import Gtk, Gdk, Gio, GLib, GObject, XApp, Pango
import os
import sys
import gettext
import threading
import time
import subprocess
import json
import requests
from urllib.parse import urlparse
import locale
import setproctitle

# Import our modules
sys.path.insert(0, '/usr/lib/hypnotix')
from common import Manager, Provider, Group, Channel, Serie, Season, TV_GROUP, MOVIES_GROUP, SERIES_GROUP, async_function, idle_function, PROVIDERS_PATH, FAVORITES_PATH
from mpv import MpvWidget
from xtream import XTream

# i18n
APP = 'hypnotix'
LOCALE_DIR = "/usr/share/locale"
locale.bindtextdomain(APP, LOCALE_DIR)
gettext.bindtextdomain(APP, LOCALE_DIR)
gettext.textdomain(APP)
_ = gettext.gettext

setproctitle.setproctitle("hypnotix")

PROVIDER_TYPE_URL = "url"
PROVIDER_TYPE_LOCAL = "local"
PROVIDER_TYPE_XTREAM = "xtream"

class Application(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='org.x.hypnotix')
        self.connect('activate', self.on_activate)
        
    def on_activate(self, app):
        self.window = MainWindow(self)
        self.window.show_all()

class MainWindow(XApp.GtkWindow):
    def __init__(self, application):
        super().__init__()
        
        self.application = application
        self.set_application(application)
        self.set_title(_("Hypnotix"))
        self.set_icon_name("hypnotix")
        self.set_default_size(1200, 800)
        
        # Settings
        self.settings = Gio.Settings(schema_id="org.x.hypnotix")
        
        # Manager
        self.manager = Manager(self.settings)
        
        # Variables
        self.selected_provider = None
        self.selected_group = None
        self.selected_channel = None
        self.providers = []
        self.favorites = []
        self.search_mode = False
        self.fullscreen = False
        
        # Load UI
        self.create_ui()
        self.load_providers()
        self.load_favorites()
        
        # Connect signals
        self.connect("key-press-event", self.on_key_press)
        self.connect("delete-event", self.on_window_delete)
        
    def create_ui(self):
        # Create main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(main_box)
        
        # Create headerbar
        self.create_headerbar()
        
        # Create main content
        content_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        main_box.pack_start(content_box, True, True, 0)
        
        # Create sidebar
        self.create_sidebar(content_box)
        
        # Create main area
        self.create_main_area(content_box)
        
        # Create status bar
        self.statusbar = Gtk.Statusbar()
        main_box.pack_end(self.statusbar, False, False, 0)
        
    def create_headerbar(self):
        headerbar = Gtk.HeaderBar()
        headerbar.set_show_close_button(True)
        headerbar.set_title(_("Hypnotix"))
        self.set_titlebar(headerbar)
        
        # Back button
        self.back_button = Gtk.Button()
        self.back_button.set_image(Gtk.Image.new_from_icon_name("go-previous-symbolic", Gtk.IconSize.BUTTON))
        self.back_button.set_tooltip_text(_("Back"))
        self.back_button.connect("clicked", self.on_back_clicked)
        self.back_button.set_sensitive(False)
        headerbar.pack_start(self.back_button)
        
        # Search button
        self.search_button = Gtk.ToggleButton()
        self.search_button.set_image(Gtk.Image.new_from_icon_name("edit-find-symbolic", Gtk.IconSize.BUTTON))
        self.search_button.set_tooltip_text(_("Search"))
        self.search_button.connect("toggled", self.on_search_toggled)
        headerbar.pack_start(self.search_button)
        
        # Menu button
        menu_button = Gtk.MenuButton()
        menu_button.set_image(Gtk.Image.new_from_icon_name("open-menu-symbolic", Gtk.IconSize.BUTTON))
        headerbar.pack_end(menu_button)
        
        # Create menu
        self.create_menu(menu_button)
        
    def create_menu(self, menu_button):
        menu = Gio.Menu()
        
        # Favorites
        menu.append(_("Favorites"), "app.favorites")
        
        # New Channel
        menu.append(_("New Channel"), "app.new_channel")
        
        menu.append_separator()
        
        # Preferences
        menu.append(_("Preferences"), "app.preferences")
        
        # Providers
        menu.append(_("Providers"), "app.providers")
        
        menu.append_separator()
        
        # Stream Information
        menu.append(_("Stream Information"), "app.stream_info")
        
        # Keyboard Shortcuts
        menu.append(_("Keyboard Shortcuts"), "app.shortcuts")
        
        menu.append_separator()
        
        # About
        menu.append(_("About"), "app.about")
        
        # Quit
        menu.append(_("Quit"), "app.quit")
        
        menu_button.set_menu_model(menu)
        
        # Connect actions
        self.create_actions()
        
    def create_actions(self):
        # Favorites action
        action = Gio.SimpleAction.new("favorites", None)
        action.connect("activate", self.on_favorites_clicked)
        self.application.add_action(action)
        
        # New Channel action
        action = Gio.SimpleAction.new("new_channel", None)
        action.connect("activate", self.on_new_channel_clicked)
        self.application.add_action(action)
        
        # Preferences action
        action = Gio.SimpleAction.new("preferences", None)
        action.connect("activate", self.on_preferences_clicked)
        self.application.add_action(action)
        
        # Providers action
        action = Gio.SimpleAction.new("providers", None)
        action.connect("activate", self.on_providers_clicked)
        self.application.add_action(action)
        
        # Stream Info action
        action = Gio.SimpleAction.new("stream_info", None)
        action.connect("activate", self.on_stream_info_clicked)
        self.application.add_action(action)
        
        # Shortcuts action
        action = Gio.SimpleAction.new("shortcuts", None)
        action.connect("activate", self.on_shortcuts_clicked)
        self.application.add_action(action)
        
        # About action
        action = Gio.SimpleAction.new("about", None)
        action.connect("activate", self.on_about_clicked)
        self.application.add_action(action)
        
        # Quit action
        action = Gio.SimpleAction.new("quit", None)
        action.connect("activate", self.on_quit_clicked)
        self.application.add_action(action)
        
    def create_sidebar(self, parent):
        # Sidebar scrolled window
        sidebar_scroll = Gtk.ScrolledWindow()
        sidebar_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sidebar_scroll.set_size_request(300, -1)
        parent.pack_start(sidebar_scroll, False, False, 0)
        
        # Sidebar box
        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sidebar_scroll.add(sidebar_box)
        
        # Provider selection
        provider_frame = Gtk.Frame()
        provider_frame.set_label(_("Providers"))
        sidebar_box.pack_start(provider_frame, False, False, 5)
        
        self.provider_combo = Gtk.ComboBoxText()
        self.provider_combo.connect("changed", self.on_provider_changed)
        provider_frame.add(self.provider_combo)
        
        # Search entry
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text(_("Search"))
        self.search_entry.connect("search-changed", self.on_search_changed)
        self.search_entry.set_no_show_all(True)
        sidebar_box.pack_start(self.search_entry, False, False, 5)
        
        # Groups/Categories list
        groups_frame = Gtk.Frame()
        groups_frame.set_label(_("Categories"))
        sidebar_box.pack_start(groups_frame, True, True, 5)
        
        groups_scroll = Gtk.ScrolledWindow()
        groups_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        groups_frame.add(groups_scroll)
        
        self.groups_listbox = Gtk.ListBox()
        self.groups_listbox.connect("row-selected", self.on_group_selected)
        groups_scroll.add(self.groups_listbox)
        
    def create_main_area(self, parent):
        # Main area paned
        self.main_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        parent.pack_start(self.main_paned, True, True, 0)
        
        # Channels area
        self.create_channels_area()
        
        # Player area
        self.create_player_area()
        
    def create_channels_area(self):
        # Channels scrolled window
        channels_scroll = Gtk.ScrolledWindow()
        channels_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        channels_scroll.set_size_request(400, -1)
        self.main_paned.pack1(channels_scroll, False, False)
        
        # Channels list
        self.channels_listbox = Gtk.ListBox()
        self.channels_listbox.connect("row-selected", self.on_channel_selected)
        channels_scroll.add(self.channels_listbox)
        
    def create_player_area(self):
        # Player box
        player_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.main_paned.pack2(player_box, True, False)
        
        # MPV widget
        try:
            self.mpv_widget = MpvWidget()
            player_box.pack_start(self.mpv_widget, True, True, 0)
        except Exception as e:
            print(f"Failed to create MPV widget: {e}")
            # Fallback to a simple label
            label = Gtk.Label(_("Video player not available"))
            label.set_size_request(640, 480)
            player_box.pack_start(label, True, True, 0)
            self.mpv_widget = None
        
        # Controls
        controls_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        controls_box.set_margin_top(5)
        controls_box.set_margin_bottom(5)
        controls_box.set_margin_left(5)
        controls_box.set_margin_right(5)
        player_box.pack_end(controls_box, False, False, 0)
        
        # Play/Pause button
        self.play_button = Gtk.Button()
        self.play_button.set_image(Gtk.Image.new_from_icon_name("media-playback-start-symbolic", Gtk.IconSize.BUTTON))
        self.play_button.connect("clicked", self.on_play_clicked)
        controls_box.pack_start(self.play_button, False, False, 2)
        
        # Stop button
        self.stop_button = Gtk.Button()
        self.stop_button.set_image(Gtk.Image.new_from_icon_name("media-playback-stop-symbolic", Gtk.IconSize.BUTTON))
        self.stop_button.connect("clicked", self.on_stop_clicked)
        controls_box.pack_start(self.stop_button, False, False, 2)
        
        # Fullscreen button
        self.fullscreen_button = Gtk.Button()
        self.fullscreen_button.set_image(Gtk.Image.new_from_icon_name("view-fullscreen-symbolic", Gtk.IconSize.BUTTON))
        self.fullscreen_button.connect("clicked", self.on_fullscreen_clicked)
        controls_box.pack_end(self.fullscreen_button, False, False, 2)
        
        # Currently playing label
        self.playing_label = Gtk.Label()
        self.playing_label.set_text(_("No provider selected"))
        self.playing_label.set_ellipsize(Pango.EllipsizeMode.END)
        controls_box.pack_start(self.playing_label, True, True, 10)
        
    def load_providers(self):
        """Load providers from settings"""
        self.providers = []
        provider_strings = self.settings.get_strv("providers")
        
        for provider_string in provider_strings:
            try:
                provider = Provider(None, provider_string)
                self.providers.append(provider)
                self.provider_combo.append_text(provider.name)
            except Exception as e:
                print(f"Error loading provider: {e}")
        
        # Set active provider
        active_provider = self.settings.get_string("active-provider")
        for i, provider in enumerate(self.providers):
            if provider.name == active_provider:
                self.provider_combo.set_active(i)
                break
        else:
            if self.providers:
                self.provider_combo.set_active(0)
                
    def load_favorites(self):
        """Load favorites from file"""
        try:
            self.favorites = self.manager.load_favorites()
        except Exception as e:
            print(f"Error loading favorites: {e}")
            self.favorites = []
            
    @async_function
    def load_provider_data(self, provider):
        """Load data for a provider"""
        try:
            self.update_status(_("Loading providers..."))
            
            if provider.type_id == PROVIDER_TYPE_XTREAM:
                # Load Xtream provider
                xtream = XTream(provider.name, provider.username, provider.password, provider.url)
                xtream.load_iptv()
                
                # Convert to our format
                provider.groups = []
                provider.channels = []
                provider.movies = []
                provider.series = []
                
                for group in xtream.groups:
                    new_group = Group(group.name)
                    new_group.group_type = group.group_type
                    new_group.channels = group.channels
                    new_group.series = group.series
                    provider.groups.append(new_group)
                
                provider.channels = xtream.channels
                provider.movies = xtream.movies
                provider.series = xtream.series
                
            else:
                # Load M3U provider
                self.update_status(_("Downloading playlist..."))
                success = self.manager.get_playlist(provider, refresh=True)
                
                if not success:
                    self.update_status(_("Failed to download playlist from %s") % provider.name)
                    return
                
                self.update_status(_("Checking playlist..."))
                if not self.manager.check_playlist(provider):
                    self.update_status(_("Invalid playlist format"))
                    return
                
                self.update_status(_("Loading channels..."))
                self.manager.load_channels(provider)
            
            # Update UI
            self.update_groups_list(provider)
            self.update_status("")
            
        except Exception as e:
            print(f"Error loading provider data: {e}")
            self.update_status(_("Failed to load provider"))
            
    @idle_function
    def update_status(self, message):
        """Update status bar"""
        context_id = self.statusbar.get_context_id("main")
        self.statusbar.pop(context_id)
        if message:
            self.statusbar.push(context_id, message)
            
    @idle_function
    def update_groups_list(self, provider):
        """Update the groups list"""
        # Clear existing groups
        for child in self.groups_listbox.get_children():
            self.groups_listbox.remove(child)
        
        # Add favorites
        row = Gtk.ListBoxRow()
        label = Gtk.Label(_("Favorites"))
        label.set_halign(Gtk.Align.START)
        label.set_margin_left(10)
        label.set_margin_right(10)
        label.set_margin_top(5)
        label.set_margin_bottom(5)
        row.add(label)
        row.provider_type = "favorites"
        self.groups_listbox.add(row)
        
        if provider:
            # Add TV Channels
            if provider.channels:
                row = Gtk.ListBoxRow()
                label = Gtk.Label(_("TV Channels (%d)") % len(provider.channels))
                label.set_halign(Gtk.Align.START)
                label.set_margin_left(10)
                label.set_margin_right(10)
                label.set_margin_top(5)
                label.set_margin_bottom(5)
                row.add(label)
                row.provider_type = "tv"
                self.groups_listbox.add(row)
            
            # Add Movies
            if provider.movies:
                row = Gtk.ListBoxRow()
                label = Gtk.Label(_("Movies (%d)") % len(provider.movies))
                label.set_halign(Gtk.Align.START)
                label.set_margin_left(10)
                label.set_margin_right(10)
                label.set_margin_top(5)
                label.set_margin_bottom(5)
                row.add(label)
                row.provider_type = "movies"
                self.groups_listbox.add(row)
            
            # Add Series
            if provider.series:
                row = Gtk.ListBoxRow()
                label = Gtk.Label(_("Series (%d)") % len(provider.series))
                label.set_halign(Gtk.Align.START)
                label.set_margin_left(10)
                label.set_margin_right(10)
                label.set_margin_top(5)
                label.set_margin_bottom(5)
                row.add(label)
                row.provider_type = "series"
                self.groups_listbox.add(row)
            
            # Add groups
            for group in provider.groups:
                row = Gtk.ListBoxRow()
                label = Gtk.Label(f"{group.name} ({len(group.channels)})")
                label.set_halign(Gtk.Align.START)
                label.set_margin_left(10)
                label.set_margin_right(10)
                label.set_margin_top(5)
                label.set_margin_bottom(5)
                row.add(label)
                row.group = group
                row.provider_type = "group"
                self.groups_listbox.add(row)
        
        self.groups_listbox.show_all()
        
    def update_channels_list(self, channels):
        """Update the channels list"""
        # Clear existing channels
        for child in self.channels_listbox.get_children():
            self.channels_listbox.remove(child)
        
        for channel in channels:
            row = Gtk.ListBoxRow()
            
            # Create channel row
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            box.set_margin_left(10)
            box.set_margin_right(10)
            box.set_margin_top(5)
            box.set_margin_bottom(5)
            
            # Channel name
            label = Gtk.Label(channel.name or channel.title or "Unknown")
            label.set_halign(Gtk.Align.START)
            label.set_ellipsize(Pango.EllipsizeMode.END)
            box.pack_start(label, True, True, 0)
            
            # Favorite button
            fav_button = Gtk.Button()
            if channel.name in self.favorites:
                fav_button.set_image(Gtk.Image.new_from_icon_name("starred-symbolic", Gtk.IconSize.BUTTON))
                fav_button.set_tooltip_text(_("Remove from favorites"))
            else:
                fav_button.set_image(Gtk.Image.new_from_icon_name("non-starred-symbolic", Gtk.IconSize.BUTTON))
                fav_button.set_tooltip_text(_("Add to favorites"))
            
            fav_button.connect("clicked", self.on_favorite_clicked, channel)
            fav_button.set_relief(Gtk.ReliefStyle.NONE)
            box.pack_end(fav_button, False, False, 0)
            
            row.add(box)
            row.channel = channel
            self.channels_listbox.add(row)
        
        self.channels_listbox.show_all()
        
    def play_channel(self, channel):
        """Play a channel"""
        if not self.mpv_widget:
            return
            
        try:
            # Set MPV options
            mpv_options = self.settings.get_string("mpv-options")
            if mpv_options:
                for option in mpv_options.split():
                    if "=" in option:
                        key, value = option.split("=", 1)
                        self.mpv_widget.mpv[key] = value
            
            # Play the channel
            self.mpv_widget.mpv.play(channel.url)
            self.selected_channel = channel
            
            # Update UI
            self.playing_label.set_text(_("Currently playing: %s") % (channel.name or channel.title))
            self.play_button.set_image(Gtk.Image.new_from_icon_name("media-playback-pause-symbolic", Gtk.IconSize.BUTTON))
            
        except Exception as e:
            print(f"Error playing channel: {e}")
            self.update_status(_("Failed to play channel"))
            
    # Event handlers
    def on_provider_changed(self, combo):
        """Handle provider selection change"""
        active = combo.get_active()
        if active >= 0 and active < len(self.providers):
            self.selected_provider = self.providers[active]
            self.settings.set_string("active-provider", self.selected_provider.name)
            self.load_provider_data(self.selected_provider)
            
    def on_group_selected(self, listbox, row):
        """Handle group selection"""
        if not row:
            return
            
        if hasattr(row, 'provider_type'):
            if row.provider_type == "favorites":
                # Show favorites
                favorite_channels = []
                if self.selected_provider:
                    all_channels = self.selected_provider.channels + self.selected_provider.movies
                    for channel in all_channels:
                        if channel.name in self.favorites:
                            favorite_channels.append(channel)
                self.update_channels_list(favorite_channels)
                
            elif row.provider_type == "tv":
                self.update_channels_list(self.selected_provider.channels)
                
            elif row.provider_type == "movies":
                self.update_channels_list(self.selected_provider.movies)
                
            elif row.provider_type == "series":
                # For series, show as channels for now
                series_channels = []
                for serie in self.selected_provider.series:
                    for episode in serie.episodes:
                        series_channels.append(episode)
                self.update_channels_list(series_channels)
                
            elif row.provider_type == "group" and hasattr(row, 'group'):
                self.update_channels_list(row.group.channels)
                
    def on_channel_selected(self, listbox, row):
        """Handle channel selection"""
        if row and hasattr(row, 'channel'):
            self.play_channel(row.channel)
            
    def on_favorite_clicked(self, button, channel):
        """Handle favorite button click"""
        if channel.name in self.favorites:
            self.favorites.remove(channel.name)
            button.set_image(Gtk.Image.new_from_icon_name("non-starred-symbolic", Gtk.IconSize.BUTTON))
            button.set_tooltip_text(_("Add to favorites"))
        else:
            self.favorites.append(channel.name)
            button.set_image(Gtk.Image.new_from_icon_name("starred-symbolic", Gtk.IconSize.BUTTON))
            button.set_tooltip_text(_("Remove from favorites"))
        
        # Save favorites
        self.manager.save_favorites(self.favorites)
        
    def on_play_clicked(self, button):
        """Handle play/pause button click"""
        if not self.mpv_widget:
            return
            
        try:
            if self.mpv_widget.mpv.pause:
                self.mpv_widget.mpv.pause = False
                button.set_image(Gtk.Image.new_from_icon_name("media-playback-pause-symbolic", Gtk.IconSize.BUTTON))
            else:
                self.mpv_widget.mpv.pause = True
                button.set_image(Gtk.Image.new_from_icon_name("media-playback-start-symbolic", Gtk.IconSize.BUTTON))
        except:
            pass
            
    def on_stop_clicked(self, button):
        """Handle stop button click"""
        if not self.mpv_widget:
            return
            
        try:
            self.mpv_widget.mpv.stop()
            self.playing_label.set_text(_("Stopped"))
            self.play_button.set_image(Gtk.Image.new_from_icon_name("media-playback-start-symbolic", Gtk.IconSize.BUTTON))
        except:
            pass
            
    def on_fullscreen_clicked(self, button):
        """Handle fullscreen button click"""
        self.toggle_fullscreen()
        
    def on_back_clicked(self, button):
        """Handle back button click"""
        # Implement navigation back
        pass
        
    def on_search_toggled(self, button):
        """Handle search toggle"""
        if button.get_active():
            self.search_entry.show()
            self.search_entry.grab_focus()
            self.search_mode = True
        else:
            self.search_entry.hide()
            self.search_mode = False
            self.search_entry.set_text("")
            
    def on_search_changed(self, entry):
        """Handle search text change"""
        search_text = entry.get_text().lower()
        
        if not search_text:
            # Show all channels
            if self.selected_provider:
                self.update_channels_list(self.selected_provider.channels)
            return
        
        # Filter channels
        filtered_channels = []
        if self.selected_provider:
            all_channels = self.selected_provider.channels + self.selected_provider.movies
            for channel in all_channels:
                if search_text in (channel.name or "").lower() or search_text in (channel.title or "").lower():
                    filtered_channels.append(channel)
        
        self.update_channels_list(filtered_channels)
        
    def on_key_press(self, widget, event):
        """Handle key press events"""
        keyval = event.keyval
        state = event.state
        
        # Ctrl+F for search
        if state & Gdk.ModifierType.CONTROL_MASK and keyval == Gdk.KEY_f:
            self.search_button.set_active(not self.search_button.get_active())
            return True
            
        # Ctrl+Q for quit
        if state & Gdk.ModifierType.CONTROL_MASK and keyval == Gdk.KEY_q:
            self.quit_application()
            return True
            
        # F11 for fullscreen
        if keyval == Gdk.KEY_F11:
            self.toggle_fullscreen()
            return True
            
        # F1 for about
        if keyval == Gdk.KEY_F1:
            self.show_about()
            return True
            
        # F2 for stream info
        if keyval == Gdk.KEY_F2:
            self.show_stream_info()
            return True
            
        # Escape to exit fullscreen
        if keyval == Gdk.KEY_Escape and self.fullscreen:
            self.unfullscreen()
            self.fullscreen = False
            return True
            
        return False
        
    def toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        if self.fullscreen:
            self.unfullscreen()
            self.fullscreen = False
        else:
            self.fullscreen()
            self.fullscreen = True
            
    def on_window_delete(self, widget, event):
        """Handle window delete event"""
        self.quit_application()
        return False
        
    def quit_application(self):
        """Quit the application"""
        if self.mpv_widget:
            try:
                self.mpv_widget.mpv.quit()
            except:
                pass
        self.application.quit()
        
    # Menu actions
    def on_favorites_clicked(self, action, param):
        """Show favorites"""
        # Select favorites in groups list
        for row in self.groups_listbox.get_children():
            if hasattr(row, 'provider_type') and row.provider_type == "favorites":
                self.groups_listbox.select_row(row)
                break
                
    def on_new_channel_clicked(self, action, param):
        """Show new channel dialog"""
        dialog = NewChannelDialog(self)
        response = dialog.run()
        dialog.destroy()
        
    def on_preferences_clicked(self, action, param):
        """Show preferences dialog"""
        dialog = PreferencesDialog(self)
        response = dialog.run()
        dialog.destroy()
        
    def on_providers_clicked(self, action, param):
        """Show providers dialog"""
        dialog = ProvidersDialog(self)
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            # Reload providers
            self.provider_combo.remove_all()
            self.load_providers()
        dialog.destroy()
        
    def on_stream_info_clicked(self, action, param):
        """Show stream information"""
        self.show_stream_info()
        
    def on_shortcuts_clicked(self, action, param):
        """Show keyboard shortcuts"""
        self.show_shortcuts()
        
    def on_about_clicked(self, action, param):
        """Show about dialog"""
        self.show_about()
        
    def on_quit_clicked(self, action, param):
        """Quit application"""
        self.quit_application()
        
    def show_about(self):
        """Show about dialog"""
        about = Gtk.AboutDialog()
        about.set_transient_for(self)
        about.set_program_name(_("Hypnotix"))
        about.set_version("4.9")
        about.set_comments(_("Watch TV"))
        about.set_website("https://github.com/linuxmint/hypnotix")
        about.set_logo_icon_name("hypnotix")
        about.run()
        about.destroy()
        
    def show_stream_info(self):
        """Show stream information"""
        if not self.selected_channel or not self.mpv_widget:
            return
            
        dialog = Gtk.Dialog(_("Stream Information"), self, 0,
                           (Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE))
        dialog.set_default_size(400, 300)
        
        content = dialog.get_content_area()
        
        # Create info display
        textview = Gtk.TextView()
        textview.set_editable(False)
        buffer = textview.get_buffer()
        
        info_text = f"Channel: {self.selected_channel.name}\n"
        info_text += f"URL: {self.selected_channel.url}\n"
        
        if self.selected_channel.group_title:
            info_text += f"Group: {self.selected_channel.group_title}\n"
            
        buffer.set_text(info_text)
        
        scroll = Gtk.ScrolledWindow()
        scroll.add(textview)
        content.pack_start(scroll, True, True, 0)
        
        dialog.show_all()
        dialog.run()
        dialog.destroy()
        
    def show_shortcuts(self):
        """Show keyboard shortcuts"""
        try:
            builder = Gtk.Builder()
            builder.add_from_file("/usr/share/hypnotix/shortcuts.ui")
            shortcuts = builder.get_object("shortcuts")
            shortcuts.set_transient_for(self)
            shortcuts.show()
        except Exception as e:
            print(f"Error showing shortcuts: {e}")

class NewChannelDialog(Gtk.Dialog):
    def __init__(self, parent):
        super().__init__(_("Create a new channel"), parent, 0,
                        (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                         Gtk.STOCK_OK, Gtk.ResponseType.OK))
        
        self.set_default_size(400, 200)
        content = self.get_content_area()
        
        grid = Gtk.Grid()
        grid.set_margin_left(10)
        grid.set_margin_right(10)
        grid.set_margin_top(10)
        grid.set_margin_bottom(10)
        grid.set_row_spacing(10)
        grid.set_column_spacing(10)
        content.add(grid)
        
        # Name
        grid.attach(Gtk.Label(_("Name:")), 0, 0, 1, 1)
        self.name_entry = Gtk.Entry()
        grid.attach(self.name_entry, 1, 0, 1, 1)
        
        # URL
        grid.attach(Gtk.Label(_("URL:")), 0, 1, 1, 1)
        self.url_entry = Gtk.Entry()
        grid.attach(self.url_entry, 1, 1, 1, 1)
        
        # Logo URL
        grid.attach(Gtk.Label(_("Logo URL:")), 0, 2, 1, 1)
        self.logo_entry = Gtk.Entry()
        grid.attach(self.logo_entry, 1, 2, 1, 1)
        
        self.show_all()

class PreferencesDialog(Gtk.Dialog):
    def __init__(self, parent):
        super().__init__(_("Preferences"), parent, 0,
                        (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                         Gtk.STOCK_OK, Gtk.ResponseType.OK))
        
        self.parent = parent
        self.set_default_size(500, 400)
        content = self.get_content_area()
        
        notebook = Gtk.Notebook()
        content.add(notebook)
        
        # Playback tab
        self.create_playback_tab(notebook)
        
        # Network tab
        self.create_network_tab(notebook)
        
        self.show_all()
        
    def create_playback_tab(self, notebook):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.set_margin_left(10)
        box.set_margin_right(10)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.set_spacing(10)
        
        # MPV Options
        frame = Gtk.Frame()
        frame.set_label(_("MPV Options"))
        box.pack_start(frame, False, False, 0)
        
        mpv_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        mpv_box.set_margin_left(10)
        mpv_box.set_margin_right(10)
        mpv_box.set_margin_top(10)
        mpv_box.set_margin_bottom(10)
        frame.add(mpv_box)
        
        mpv_box.pack_start(Gtk.Label(_("List of MPV options")), False, False, 0)
        
        self.mpv_entry = Gtk.Entry()
        self.mpv_entry.set_text(self.parent.settings.get_string("mpv-options"))
        mpv_box.pack_start(self.mpv_entry, False, False, 5)
        
        notebook.append_page(box, Gtk.Label(_("Playback")))
        
    def create_network_tab(self, notebook):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.set_margin_left(10)
        box.set_margin_right(10)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.set_spacing(10)
        
        grid = Gtk.Grid()
        grid.set_row_spacing(10)
        grid.set_column_spacing(10)
        box.pack_start(grid, False, False, 0)
        
        # User Agent
        grid.attach(Gtk.Label(_("User Agent")), 0, 0, 1, 1)
        self.user_agent_entry = Gtk.Entry()
        self.user_agent_entry.set_text(self.parent.settings.get_string("user-agent"))
        grid.attach(self.user_agent_entry, 1, 0, 1, 1)
        
        # Referrer
        grid.attach(Gtk.Label(_("Referrer")), 0, 1, 1, 1)
        self.referrer_entry = Gtk.Entry()
        self.referrer_entry.set_text(self.parent.settings.get_string("http-referer"))
        grid.attach(self.referrer_entry, 1, 1, 1, 1)
        
        notebook.append_page(box, Gtk.Label(_("Network")))
        
    def run(self):
        response = super().run()
        if response == Gtk.ResponseType.OK:
            # Save settings
            self.parent.settings.set_string("mpv-options", self.mpv_entry.get_text())
            self.parent.settings.set_string("user-agent", self.user_agent_entry.get_text())
            self.parent.settings.set_string("http-referer", self.referrer_entry.get_text())
        return response

class ProvidersDialog(Gtk.Dialog):
    def __init__(self, parent):
        super().__init__(_("Providers"), parent, 0,
                        (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                         Gtk.STOCK_OK, Gtk.ResponseType.OK))
        
        self.parent = parent
        self.set_default_size(600, 400)
        content = self.get_content_area()
        
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.set_margin_left(10)
        box.set_margin_right(10)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        content.add(box)
        
        # Toolbar
        toolbar = Gtk.Toolbar()
        box.pack_start(toolbar, False, False, 0)
        
        # Add button
        add_button = Gtk.ToolButton()
        add_button.set_icon_name("list-add-symbolic")
        add_button.set_tooltip_text(_("Add a new provider..."))
        add_button.connect("clicked", self.on_add_clicked)
        toolbar.insert(add_button, -1)
        
        # Remove button
        remove_button = Gtk.ToolButton()
        remove_button.set_icon_name("list-remove-symbolic")
        remove_button.set_tooltip_text(_("Remove"))
        remove_button.connect("clicked", self.on_remove_clicked)
        toolbar.insert(remove_button, -1)
        
        # Reset button
        reset_button = Gtk.ToolButton()
        reset_button.set_icon_name("edit-undo-symbolic")
        reset_button.set_tooltip_text(_("Reset to defaults..."))
        reset_button.connect("clicked", self.on_reset_clicked)
        toolbar.insert(reset_button, -1)
        
        # Providers list
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        box.pack_start(scroll, True, True, 5)
        
        self.providers_listbox = Gtk.ListBox()
        scroll.add(self.providers_listbox)
        
        self.load_providers_list()
        self.show_all()
        
    def load_providers_list(self):
        """Load providers into the list"""
        for child in self.providers_listbox.get_children():
            self.providers_listbox.remove(child)
            
        for provider in self.parent.providers:
            row = Gtk.ListBoxRow()
            
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            box.set_margin_left(10)
            box.set_margin_right(10)
            box.set_margin_top(5)
            box.set_margin_bottom(5)
            
            name_label = Gtk.Label(provider.name)
            name_label.set_halign(Gtk.Align.START)
            name_label.set_markup(f"<b>{provider.name}</b>")
            box.pack_start(name_label, False, False, 0)
            
            url_label = Gtk.Label(provider.url)
            url_label.set_halign(Gtk.Align.START)
            url_label.set_ellipsize(Pango.EllipsizeMode.END)
            box.pack_start(url_label, False, False, 0)
            
            row.add(box)
            row.provider = provider
            self.providers_listbox.add(row)
            
        self.providers_listbox.show_all()
        
    def on_add_clicked(self, button):
        """Add new provider"""
        dialog = ProviderEditDialog(self, None)
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            provider_info = dialog.get_provider_info()
            provider = Provider(None, provider_info)
            self.parent.providers.append(provider)
            self.save_providers()
            self.load_providers_list()
        dialog.destroy()
        
    def on_remove_clicked(self, button):
        """Remove selected provider"""
        row = self.providers_listbox.get_selected_row()
        if row and hasattr(row, 'provider'):
            # Confirm deletion
            dialog = Gtk.MessageDialog(self, 0, Gtk.MessageType.QUESTION,
                                     Gtk.ButtonsType.YES_NO,
                                     _("Are you sure you want to delete this provider?"))
            response = dialog.run()
            dialog.destroy()
            
            if response == Gtk.ResponseType.YES:
                self.parent.providers.remove(row.provider)
                self.save_providers()
                self.load_providers_list()
                
    def on_reset_clicked(self, button):
        """Reset to default providers"""
        dialog = Gtk.MessageDialog(self, 0, Gtk.MessageType.QUESTION,
                                 Gtk.ButtonsType.YES_NO,
                                 _("Are you sure you want to reset to the default providers?"))
        response = dialog.run()
        dialog.destroy()
        
        if response == Gtk.ResponseType.YES:
            # Reset to default
            default_providers = ['Free-TV:::url:::https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8:::::::::']
            self.parent.settings.set_strv("providers", default_providers)
            
            # Reload
            self.parent.providers = []
            for provider_string in default_providers:
                provider = Provider(None, provider_string)
                self.parent.providers.append(provider)
            
            self.load_providers_list()
            
    def save_providers(self):
        """Save providers to settings"""
        provider_strings = []
        for provider in self.parent.providers:
            provider_strings.append(provider.get_info())
        self.parent.settings.set_strv("providers", provider_strings)

class ProviderEditDialog(Gtk.Dialog):
    def __init__(self, parent, provider):
        title = _("Edit %s") % provider.name if provider else _("Add a new provider")
        super().__init__(title, parent, 0,
                        (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                         Gtk.STOCK_OK, Gtk.ResponseType.OK))
        
        self.provider = provider
        self.set_default_size(400, 300)
        content = self.get_content_area()
        
        grid = Gtk.Grid()
        grid.set_margin_left(10)
        grid.set_margin_right(10)
        grid.set_margin_top(10)
        grid.set_margin_bottom(10)
        grid.set_row_spacing(10)
        grid.set_column_spacing(10)
        content.add(grid)
        
        row = 0
        
        # Name
        grid.attach(Gtk.Label(_("Name:")), 0, row, 1, 1)
        self.name_entry = Gtk.Entry()
        if provider:
            self.name_entry.set_text(provider.name)
        grid.attach(self.name_entry, 1, row, 1, 1)
        row += 1
        
        # Type
        grid.attach(Gtk.Label(_("Type:")), 0, row, 1, 1)
        self.type_combo = Gtk.ComboBoxText()
        self.type_combo.append_text("M3U URL")
        self.type_combo.append_text("Local M3U File")
        self.type_combo.append_text("Xtream API")
        self.type_combo.set_active(0)
        self.type_combo.connect("changed", self.on_type_changed)
        grid.attach(self.type_combo, 1, row, 1, 1)
        row += 1
        
        # URL
        self.url_label = Gtk.Label(_("URL:"))
        grid.attach(self.url_label, 0, row, 1, 1)
        self.url_entry = Gtk.Entry()
        if provider:
            self.url_entry.set_text(provider.url)
        grid.attach(self.url_entry, 1, row, 1, 1)
        row += 1
        
        # Username (for Xtream)
        self.username_label = Gtk.Label(_("Username:"))
        grid.attach(self.username_label, 0, row, 1, 1)
        self.username_entry = Gtk.Entry()
        if provider:
            self.username_entry.set_text(provider.username)
        grid.attach(self.username_entry, 1, row, 1, 1)
        row += 1
        
        # Password (for Xtream)
        self.password_label = Gtk.Label(_("Password:"))
        grid.attach(self.password_label, 0, row, 1, 1)
        self.password_entry = Gtk.Entry()
        self.password_entry.set_visibility(False)
        if provider:
            self.password_entry.set_text(provider.password)
        grid.attach(self.password_entry, 1, row, 1, 1)
        row += 1
        
        # EPG
        grid.attach(Gtk.Label(_("EPG:")), 0, row, 1, 1)
        self.epg_entry = Gtk.Entry()
        if provider:
            self.epg_entry.set_text(provider.epg)
        grid.attach(self.epg_entry, 1, row, 1, 1)
        
        self.on_type_changed(self.type_combo)
        self.show_all()
        
    def on_type_changed(self, combo):
        """Handle type change"""
        active = combo.get_active()
        
        if active == 0:  # M3U URL
            self.url_label.set_text(_("URL:"))
            self.username_label.hide()
            self.username_entry.hide()
            self.password_label.hide()
            self.password_entry.hide()
        elif active == 1:  # Local M3U File
            self.url_label.set_text(_("Path:"))
            self.username_label.hide()
            self.username_entry.hide()
            self.password_label.hide()
            self.password_entry.hide()
        elif active == 2:  # Xtream API
            self.url_label.set_text(_("URL:"))
            self.username_label.show()
            self.username_entry.show()
            self.password_label.show()
            self.password_entry.show()
            
    def get_provider_info(self):
        """Get provider info string"""
        name = self.name_entry.get_text()
        url = self.url_entry.get_text()
        username = self.username_entry.get_text()
        password = self.password_entry.get_text()
        epg = self.epg_entry.get_text()
        
        active = self.type_combo.get_active()
        if active == 0:
            type_id = "url"
        elif active == 1:
            type_id = "local"
        else:
            type_id = "xtream"
            
        return f"{name}:::{type_id}:::{url}:::{username}:::{password}:::{epg}"

def main():
    # Set up application
    app = Application()
    
    # Run application
    try:
        app.run(sys.argv)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()