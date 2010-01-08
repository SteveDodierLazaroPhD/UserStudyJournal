
import gtk
import sys
from datetime import date


import calview
import rdate
import rdate_z

def selection_callback(history, i):
    if i < len(history):
        selection_date = history[i][0]
        if isinstance(selection_date, int): 
            selection_date = date.fromtimestamp(selection_date).strftime("%d/%B")
        print "%d day %s has %s events\n" % (i,selection_date, history[i][1])

def date_changed(*args, **kwargs):
    print "Date Changed"
        
if __name__ == "__main__":
    cal = calview.CalWidget()
    window = gtk.Window()
    window.add(cal)
    if len(sys.argv) > 1 and sys.argv[1] == "z":
        rdate_z.datelist(30, cal.scrollcal.update_data)
    else:
        cal.scrollcal.update_data(rdate.datelist(150))
    cal.scrollcal.connect_selection_callback(selection_callback)
    cal.scrollcal.connect("date-set", date_changed)
    window.show_all()
    gtk.main()
