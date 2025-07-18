#!/usr/bin/python3

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, GObject
import locale
import threading
import time

try:
    import mpv
    MPV_AVAILABLE = True
except ImportError:
    MPV_AVAILABLE = False
    print("python-mpv not available, video playback will be limited")

class MpvWidget(Gtk.DrawingArea):
    """GTK widget for MPV video player"""
    
    def __init__(self):
        super().__init__()
        
        if not MPV_AVAILABLE:
            raise Exception("MPV not available")
        
        self.mpv = None
        self.mpv_opengl_cb_context = None
        
        # Set up the widget
        self.set_can_focus(True)
        self.set_events(self.get_events() | 
                       gi.repository.Gdk.EventMask.BUTTON_PRESS_MASK |
                       gi.repository.Gdk.EventMask.BUTTON_RELEASE_MASK |
                       gi.repository.Gdk.EventMask.KEY_PRESS_MASK |
                       gi.repository.Gdk.EventMask.KEY_RELEASE_MASK |
                       gi.repository.Gdk.EventMask.SCROLL_MASK)
        
        # Connect signals
        self.connect("realize", self.on_realize)
        self.connect("unrealize", self.on_unrealize)
        self.connect("draw", self.on_draw)
        self.connect("button-press-event", self.on_button_press)
        self.connect("key-press-event", self.on_key_press)
        self.connect("scroll-event", self.on_scroll)
        
        # Initialize MPV
        self.init_mpv()
        
    def init_mpv(self):
        """Initialize MPV player"""
        try:
            # Locale workaround
            locale.setlocale(locale.LC_NUMERIC, 'C')
            
            self.mpv = mpv.MPV(
                wid=str(self.get_window().get_xid()) if self.get_window() else "0",
                vo='x11',
                hwdec='auto-safe',
                input_default_bindings=True,
                input_vo_keyboard=True,
                osc=True
            )
            
            # Set up event handlers
            @self.mpv.event_callback('playback-restart')
            def on_playback_restart(event):
                GLib.idle_add(self.queue_draw)
                
            @self.mpv.event_callback('file-loaded')
            def on_file_loaded(event):
                GLib.idle_add(self.queue_draw)
                
        except Exception as e:
            print(f"Failed to initialize MPV: {e}")
            self.mpv = None
            
    def on_realize(self, widget):
        """Handle widget realization"""
        if self.mpv and self.get_window():
            try:
                self.mpv.wid = str(self.get_window().get_xid())
            except Exception as e:
                print(f"Error setting MPV window ID: {e}")
                
    def on_unrealize(self, widget):
        """Handle widget unrealization"""
        if self.mpv:
            try:
                self.mpv.terminate()
            except:
                pass
                
    def on_draw(self, widget, cr):
        """Handle draw event"""
        if not self.mpv:
            # Draw a black background
            cr.set_source_rgb(0, 0, 0)
            cr.paint()
            return False
            
        # MPV handles drawing
        return False
        
    def on_button_press(self, widget, event):
        """Handle button press events"""
        self.grab_focus()
        
        if event.type == gi.repository.Gdk.EventType.DOUBLE_BUTTON_PRESS:
            # Double click to toggle fullscreen
            parent = self.get_toplevel()
            if parent and hasattr(parent, 'toggle_fullscreen'):
                parent.toggle_fullscreen()
                
        return False
        
    def on_key_press(self, widget, event):
        """Handle key press events"""
        if not self.mpv:
            return False
            
        # Let MPV handle key events
        return False
        
    def on_scroll(self, widget, event):
        """Handle scroll events"""
        if not self.mpv:
            return False
            
        # Volume control with scroll wheel
        try:
            if event.direction == gi.repository.Gdk.ScrollDirection.UP:
                current_volume = self.mpv.volume or 100
                self.mpv.volume = min(100, current_volume + 5)
            elif event.direction == gi.repository.Gdk.ScrollDirection.DOWN:
                current_volume = self.mpv.volume or 100
                self.mpv.volume = max(0, current_volume - 5)
        except:
            pass
            
        return True
        
    def play(self, url):
        """Play a URL"""
        if not self.mpv:
            return
            
        try:
            self.mpv.play(url)
        except Exception as e:
            print(f"Error playing URL {url}: {e}")
            
    def stop(self):
        """Stop playback"""
        if not self.mpv:
            return
            
        try:
            self.mpv.stop()
        except:
            pass
            
    def pause(self):
        """Pause/unpause playback"""
        if not self.mpv:
            return
            
        try:
            self.mpv.pause = not self.mpv.pause
        except:
            pass
            
    def set_property(self, prop, value):
        """Set MPV property"""
        if not self.mpv:
            return
            
        try:
            setattr(self.mpv, prop, value)
        except Exception as e:
            print(f"Error setting MPV property {prop}={value}: {e}")
            
    def get_property(self, prop):
        """Get MPV property"""
        if not self.mpv:
            return None
            
        try:
            return getattr(self.mpv, prop)
        except:
            return None

# Fallback widget when MPV is not available
class FallbackWidget(Gtk.DrawingArea):
    """Fallback widget when MPV is not available"""
    
    def __init__(self):
        super().__init__()
        self.set_size_request(640, 480)
        self.connect("draw", self.on_draw)
        
    def on_draw(self, widget, cr):
        """Draw fallback content"""
        allocation = widget.get_allocation()
        
        # Draw black background
        cr.set_source_rgb(0, 0, 0)
        cr.rectangle(0, 0, allocation.width, allocation.height)
        cr.fill()
        
        # Draw message
        cr.set_source_rgb(1, 1, 1)
        cr.select_font_face("Sans", 0, 0)
        cr.set_font_size(16)
        
        text = "Video player not available"
        text_extents = cr.text_extents(text)
        x = (allocation.width - text_extents.width) / 2
        y = (allocation.height + text_extents.height) / 2
        
        cr.move_to(x, y)
        cr.show_text(text)
        
        return False
        
    def play(self, url):
        """Dummy play method"""
        print(f"Would play: {url}")
        
    def stop(self):
        """Dummy stop method"""
        pass
        
    def pause(self):
        """Dummy pause method"""
        pass

# Factory function
def create_mpv_widget():
    """Create MPV widget or fallback"""
    if MPV_AVAILABLE:
        try:
            return MpvWidget()
        except Exception as e:
            print(f"Failed to create MPV widget: {e}")
            return FallbackWidget()
    else:
        return FallbackWidget()