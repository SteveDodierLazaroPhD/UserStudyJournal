#!/usr/bin/env python

## Copyright (C) 2009  Randal Barlow
##
##
## This program is free software: you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation, either version 3 of the License, or
## (at your option) any later version.

## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.

## You should have received a copy of the GNU General Public License
## along with this program.  If not, see <http://www.gnu.org/licenses/

"""
Takes a two dementional tuple or list and turns it into a graph based on 
history[n][1]'s size

# history = [[raw_date, nitems]]
"""

import cairo
import gobject
import gtk
import math
import time
import datetime


def check_for_new_month(date):
    print type(date)
    if datetime.date.fromtimestamp(float(date)).strftime("%d") == 1:
        print "new month"
        return True
    return False


def get_gtk_rgba(style, palette, i):
    """Takes a gtk style and returns a RGB tuple
    
    Arguments:
    - style: a gtk_style object
    - palette: a string representing the palette you want to pull a color from
        Example: "bg", "fg"
    """
    f = lambda num: num/65535.0
    
    color = getattr(style, palette)[i]
    if isinstance(color, gtk.gdk.Color):
        return (f(color.red), f(color.green), f(color.blue), 1)
    else: raise TypeError("Not a valid gtk.gdk.Color")


class ScrollCal(gtk.DrawingArea):
    """
    A calendar which is represented by a list of dimensions and dates
    """
    padding = 4
    ypad = 10
    wcolumn = 10
    xincrement = wcolumn + padding
    max_width = xincrement

    def __init__(self, history):
        """
        
        Arguments:
        - history: The ScrollCals two dimensional list of dates and nitems
        """
        super(ScrollCal, self).__init__()
        self.add_events(gtk.gdk.BUTTON_PRESS_MASK)
        self.connect("expose_event", self.expose)
        self.connect("button-press-event", self.clicked)
        self.update_data(history, draw = False)
        gobject.signal_new("date-set", ScrollCal,
                           gobject.SIGNAL_RUN_LAST,
                           gobject.TYPE_NONE,())


    def update_data(self, history = None, draw = True):
        """
        Sets the objects history attribute or calls update() on the current history object
        then queues a draw 
        """
        if history:
            self.history = history
            self.largest = 1
            for date, nitems in self.history:
                if nitems > self.largest: self.largest = nitems
            self.max_width = self.xincrement + (self.xincrement *len(history))
        else:
            self.history.update()
        if draw: self.queue_draw()

    def expose(self, widget, event, selected = None):        
        # Default hilight to the final 3 items
        if selected == None:
            selected = len(self.history)-3

        context = widget.window.cairo_create()
        # Set the source to the background color
        context.set_source_rgba(*get_gtk_rgba(self.style, "bg", 0))
        context.set_operator(cairo.OPERATOR_SOURCE)
        context.paint()
        # set a clip region for the expose event
        context.rectangle(event.area.x, event.area.y, event.area.width, event.area.height)
        context.clip()
        
        x = self.xincrement
        y = event.area.height
        color = get_gtk_rgba(self.style, "text", 4)
        
        for date, nitems in self.history:
            #if check_for_new_month(date):
            #    print "new month", date
            if nitems > 0:
                self.draw_column(context, x, event.area.height, nitems, color)
            x += self.xincrement

        # Draw over the selected items
        self.draw_selected(context, selected, event.area.height)
        if x > event.area.width: # Check for resize
            self.set_size_request(x+self.xincrement, event.area.height)

        #self.max_width = x # remove me

    def draw_column(self, context, x, maxheight, nitems, color):
        """
        Draws a columns at x with height based on nitems, and maxheight
        
        Arguments:
        - context: The drawingarea's cairo context from the expose event
        - x: The current position in the image
        - maxheight: The event areas height
        - nitems: The number of items in the column to be drawn
        - color: A RGBA tuple
            Example: (0.3, 0.4, 0.8, 1)
        """
        height = ((float(nitems)/self.largest)*maxheight) - self.ypad
        radius = 2.1
        y = maxheight - height
        # Draw
        context.set_source_rgba(*color)
        context.move_to(x + radius, y)
        context.new_sub_path()
        context.arc(radius + x, radius + y, radius, math.pi, 3 * math.pi /2)
        context.arc(x + self.wcolumn - radius, radius + y, radius, 3 * math.pi / 2, 0)
        context.rectangle(x, y+radius, self.wcolumn, height)
        context.close_path()
        context.fill()

    def draw_selected(self, context, i, height):
        """
        hilights a selected area
        
        Arguments:
        - context: The drawingarea's cairo context from the expose event
        - i: The position in history of the object where you want to BEGIN
             hilighting
        - height: The event areas height
        """
        
        context.set_source_rgba(*get_gtk_rgba(self.style, "bg", 3))
        # Find current position
        x = (i * self.xincrement) + self.xincrement
        y = 0
        radius = 3

        context.arc(radius + x - 2, radius + y, radius, math.pi, 3 * math.pi /2)
        context.arc(x+(3 * self.xincrement) - radius -2, radius + y, radius, 3 * math.pi / 2, 0)
        context.rectangle(x, y+radius, self.wcolumn, height)        
        context.rectangle(x-2, radius + y, (3 * self.xincrement), height)
        context.fill()
        
        color = get_gtk_rgba(self.style, "text", 1)
        #color = (0.97, 0.97, 0.97, 1)
        # Prevent drawing additional columns for i > 2
        if x >= 1: 
            self.draw_column(context, x, height, self.history[i][1], color)
        if x >= 0:
            self.draw_column(context, x + self.xincrement, height, self.history[i+1][1], color)
        self.draw_column(context, x+(2 * self.xincrement), height, self.history[i+2][1], color)
    
    def set_selection(self, i):
        self.connect("expose_event", self.expose, i)
        self.queue_draw()
        self.emit("date-set")
        
    def selection_callback(self, history, i):
        """
        A demo callback, either rewrite this or use connect_selection_callback
        """
        print "day %s has %s events\n" % (history[i][0], history[i][1])
    
    def connect_selection_callback(self, callback):
        """
        Connect a callback for clicked to call. clicked passes this widget,
        a history list, and i to the function
        """
        if callable(callback):
            self.selection_callback = callback
        else:
            raise TypeError("Callback is not a function")
        
    def clicked(self, widget, event, *args, **kwargs):
        """Handles click events

        By wrapping this and using the returned location you can do nifty stuff
        with the history object
        
        Calls a calback set by connect_selection_callback
        """
        location = int((event.x - self.xincrement) / self.xincrement)
        if location == 2:
            self.connect("expose_event", self.expose, 0)
            self.queue_draw()
        elif location < len(self.history):
            self.connect("expose_event", self.expose, location - 2)
            self.queue_draw()
        self.emit("date-set")
        if callable(self.selection_callback):
            self.selection_callback(self.history, location)
    

    
class CalWidget(gtk.HBox):
    def scroll_viewport(self, widget, viewport, scroll_cal, value, *args, **kwargs):
        """Broken for now
        """
        adjustment = viewport.get_hadjustment()
        page_size = adjustment.get_page_size()
        if value < 1:
            newadjval = 0 if value > adjustment.value else (adjustment.value + value)
        elif adjustment.value + page_size > scroll_cal.max_width - value:
            newadjval = scroll_cal.max_width - page_size
        else:
            newadjval = adjustment.value + value
        adjustment.set_value(newadjval)

    def __init__(self):
        super(gtk.HBox, self).__init__()
        port = gtk.Viewport()
        port.set_shadow_type(gtk.SHADOW_NONE)
        port.set_size_request(600,60) 
        self.scrollcal = ScrollCal([[0, 0]])
        port.add(self.scrollcal)
        # Draw buttons
        b1 = gtk.Button()
        b1.add(gtk.Arrow(gtk.ARROW_LEFT, gtk.SHADOW_NONE))
        b1.set_relief(gtk.RELIEF_NONE)
        b1.set_focus_on_click(False)
    
        b2 = gtk.Button()
        b2.add(gtk.Arrow(gtk.ARROW_RIGHT, gtk.SHADOW_NONE))
        b2.set_relief(gtk.RELIEF_NONE)
        b2.set_focus_on_click(False)
    
        b1.connect("clicked", self.scroll_viewport, port, self.scrollcal, -100)
        b2.connect("clicked", self.scroll_viewport, port, self.scrollcal, 100)
        
        self.pack_start(b1, False, False)
        self.pack_start(port, True, True)    
        self.pack_end(b2, False, False)
           
        adj = port.get_hadjustment()    
        adj.set_upper(self.scrollcal.max_width)
        adj.set_value(1)
        adj.set_value(self.scrollcal.max_width - adj.page_size)

cal = CalWidget()