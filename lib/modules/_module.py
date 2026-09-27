#!/usr/bin/env python

# module parent class.
# All modules should inherit from this class.

from .. import hud_graphics
from ..common.dataship.dataship import Dataship
import pygame


class Module:
    def __init__(self):
        self.name = "Module"
        self.moduleVersion = 1.0
        self.width = 640
        self.height = 480
        self.pygamescreen = 0
        self.x = 0
        self.y = 0
        self.buttons = [] # list of buttons if this module has any
        self.button_font_size = 20


    def initMod(self, pygamescreen, width, height):
        self.pygamescreen = pygamescreen
        self.width = width
        self.height = height
        self.widthCenter = width / 2
        self.heightCenter = height / 2


    def processEvent(self, event):
        print(("processing module Event %s" % (event.key)))

    def draw(self, aircraft, smartdisplay):
        print("module parent")

    def setting(self, key, value):
        print("module setting")

    def clear(self):
        print("Clear screen")

    def resize(self, width, height):
        self.width = width
        self.height = height
        self.widthCenter = width / 2
        self.heightCenter = height / 2

    def getDrawSurface(self, pos):
        '''
        Return a surface that maps directly onto the display at pos, sized to this module.
        Drawing to it writes straight to the screen (no per-frame fill + blit of a
        full size temp surface) and is clipped to the module bounds.
        Coordinates are local to the module (0,0 = top left of module).
        Returns None if the module is not fully inside the top/left of the screen,
        in which case the caller should fall back to its own surface.
        '''
        x, y = int(pos[0] or 0), int(pos[1] or 0)
        screen = self.pygamescreen
        key = (id(screen), screen.get_size(), x, y, self.width, self.height)
        if getattr(self, "_draw_surface_key", None) == key:
            return self._draw_surface
        self._draw_surface_key = key
        self._draw_surface = None
        if x >= 0 and y >= 0:
            rect = pygame.Rect(x, y, int(self.width), int(self.height)).clip(screen.get_rect())
            if rect.width > 0 and rect.height > 0:
                self._draw_surface = screen.subsurface(rect)
        return self._draw_surface

    # return a dict of objects that are used to configure the module.
    def get_module_options(self):
        return {}

    ##########################################################
    # add a button to the module
    ##########################################################
    def buttonAdd(self, id, text, function = None, pos=None, x=-1, y=-1, width=0, height=0, newRow=False, center=False, selected=False, type="button"):
        # make sure the button_surface exists
        if not hasattr(self, 'button_surface'):
            self.buttonsInit()

        # Calculate the button width based on text if width is 0
        label_width = self.button_font.size(text)[0]
        if width == 0:
            width = label_width + 10  # Add 5px padding on each side
        else:
            width = max(width, label_width + 10)  # Ensure the width is at least as wide as the text plus padding

        # if height is 0, then set it to the height of the text
        if height == 0:
            height = self.button_font.size(text)[1] + 10

        # Find the last button's position
        last_button = None if len(self.buttons) == 0 else self.buttons[-1]
 
        # "TopL", "TopM", "TopR",
        # "MidL", "MidM", "MidR",
        # "BotL", "BotM", "BotR"

        if pos is not None:
            if pos == "TopL":
                x = 10
                y = 10
            elif pos == "TopM":
                x = (self.width / 2) - (width / 2)
                y = 10
            elif pos == "TopR":
                x = self.width - width - 10
                y = 10
            elif pos == "MidL":
                x = 10
                y = (self.height / 2) - (height / 2)
            elif pos == "MidM":
                x = (self.width / 2) - (width / 2)
                y = (self.height / 2) - (height / 2)
            elif pos == "MidR":
                x = self.width - width - 10
                y = (self.height / 2) - (height / 2)
            elif pos == "BotL":
                x = 10
                y = self.height - height - 10
            elif pos == "BotM":
                x = (self.width / 2) - (width / 2)
                y = self.height - height - 10
            elif pos == "BotR":
                x = self.width - width - 10
                y = self.height - height - 10

        # Handle newRow
        if newRow:
            y = (last_button['y'] + last_button['height'] + 10) if last_button else 10
            x = 10
        elif pos is None:
            if last_button:
                x = last_button['x'] + last_button['width'] + 10
                y = last_button['y']
            else:
                x = 10
                y = 10

        # Handle centering
        if center:
            row_buttons = [b for b in self.buttons if b['y'] == y] # get all buttons in this row
            row_width = sum(b['width'] for b in row_buttons) + width + ((len(row_buttons) + 1) * 10)
            x = (self.width - row_width) / 2 + sum(b['width'] for b in row_buttons) + (len(row_buttons) * 10)

        if type == "label":
            draw_background = False
        else:
            draw_background = True

        button = {  
            "id": id,
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "text": text,
            "function": function,
            "selected": False,
            "center": center,
            "newRow": newRow,
            "type": type,
            "draw_background": draw_background
        }
        self.buttons.append(button)

    # clear all buttons
    def buttonsClear(self):
        self.buttons = []

    # draw all buttons (if any)
    def buttonsDraw(self, dataship: Dataship, smartdisplay, pos=(0,0)):
        self.button_surface.fill((0,0,0,0))
        # draw buttons
        last_y = 0
        for button in self.buttons: 
            if button["selected"]:
                color = (0,200,0)
                text_color = (0,0,0)
            else:
                color = (50,50,50)
                text_color = (200,200,200)
            if button["draw_background"]: # draw background?
                pygame.draw.rect(self.button_surface, color, (button["x"], button["y"], button["width"], button["height"]), 0, border_radius=5)
            # draw text
            text = self.button_font.render(button["text"], True, text_color)
            self.button_surface.blit(text, (button["x"] + (button["width"]/2 - text.get_width()/2), button["y"] + (button["height"]/2 - text.get_height()/2)))
            last_y = button["y"] + button["height"]
        self.buttonLastY = last_y  # save the last y position for use by modules that need to add buttons after this one
        self.pygamescreen.blit(self.button_surface, pos, special_flags=pygame.BLEND_ALPHA_SDL2)

    # initialize the button surface and font. this lets the module know we are going to be using buttons.
    def buttonsInit(self):
        self.buttons = []
        self.button_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        self.button_font = pygame.font.SysFont("Monospace", self.button_font_size)
    
    # check if a click was on a button and call the button's function if it was
    def buttonsCheckClick(self, dataship: Dataship, mx, my, buttonNum):
        for button in self.buttons:
            if button["x"] <= mx <= button["x"] + button["width"] and button["y"] <= my <= button["y"] + button["height"]:
                if button["function"]:
                    button["function"]( dataship, button )
                return True
        return False
    
    # set a button to selected
    def buttonSelected(self, id, selected=True):
        for button in self.buttons:
            if button["id"] == id:
                button["selected"] = selected
                return

    def get_nested_attr(self, obj, attr):
        parts = attr.split('.')
        for part in parts:
            if part.endswith('()'):
                # It's a function call
                func_name = part[:-2]
                obj = getattr(obj, func_name)()
            elif part.endswith('<obj>'):
                # It's an object
                obj = getattr(obj, part[:-5])
            elif part.endswith(']'):
                # It's an index. example: "gpsData[0]"
                # parse the index from the string
                index = part[1:-1]
                # remove the beginning of the string until the first [
                index = index[index.find('[')+1:]
                # get the name of the object (from part) example: gpsData
                name = part[:part.find('[')]
                # get the value
                obj = getattr(obj, name)[int(index)]
                #print(f"obj: {obj}")
            else:
                obj = getattr(obj, part)
        return obj

    def format_object(self,obj):
        # check if None
        if obj is None:
            obj = "None"
        else:
            sub_vars = obj.__dict__
            final_value = ""
            for sub_var in sub_vars:
                # check if it starts with _ then skip it.
                if sub_var.startswith('_'):
                    continue
                # check if it has a __dict__.. if so skip it cause it's probably a child object. (for now...)
                if hasattr(sub_vars[sub_var], '__dict__'):
                    continue
                final_value += f"{sub_var}: {sub_vars[sub_var]}\n"
            obj = final_value
        return obj

    def special_format_specifier(self, theVariable: str, format_specifier: str, dataship: Dataship):
        """
        Handle special format specifiers.
        """
        if format_specifier == "kts":
            # convert mph to knots.
            return f"{theVariable * 0.868976:0.0f}"
        elif format_specifier == "kph":
            # convert mph to kph. (kilometers per hour)
            return f"{theVariable * 1.60934:0.0f}"
        elif format_specifier == "mph":
            # convert mph .. it's already in mph.
            return f"{theVariable:0.0f}"
        elif format_specifier == "km":
            # convert miles to kilometers.
            return f"{theVariable * 1.60934:0.1f}"
        elif format_specifier == "nm":
            # convert statute miles to nautical miles.
            return f"{theVariable * 0.868976:0.1f}"
        elif format_specifier == "ft":
            # it's already in feet.
            return f"{theVariable:0.1f}"
        elif format_specifier == "m":
            # convert feet to meters.
            return f"{theVariable * 0.3048:0.1f}"
        elif format_specifier == "c":
            # convert fahrenheit to celsius.
            return f"{((theVariable - 32) * 5/9):0.1f}"
        elif format_specifier == "f":
            # it's already in fahrenheit.
            return f"{theVariable:0.1f}"
        elif format_specifier == "10th":
            # round to the nearest 10.
            return f"{round(theVariable / 10) * 10:0.0f}"
        else:
            # else just use the built in python format specifier.
            return f"{theVariable:{format_specifier}}"

    def parse_text(self, inputText: str, dataship: Dataship):
        """
        Parse text with variables and functions.
        Variables are enclosed in curly braces.
        Functions are enclosed in parentheses.
        Objects are enclosed in angle brackets.
        Indexes are enclosed in square brackets.
        supported format specifiers:
        %d - integer
        %f - float
        %s - string
        %t - tuple
        %l - list
        %d - dictionary
        examples:
        {gpsData.latitude}
        {gpsData.latitude:0.2f} # format to 2 decimal places
        {airData[0].IAS:kts}
        """
        result = inputText
        # Find all variables enclosed in curly braces
        start = 0
        while True:
            open_brace = result.find('{', start)
            if open_brace == -1:
                break
            close_brace = result.find('}', open_brace)
            if close_brace == -1:
                break
                
            variable_name = result[open_brace + 1:close_brace]
            if "%" in variable_name:
                variable_name, format_specifier = variable_name.split("%")
            elif ":" in variable_name:
                variable_name, special_format_specifier = variable_name.split(":")
                format_specifier = None
            else:
                format_specifier = None
                special_format_specifier = None

            try:
                if variable_name == "self":
                    variable_value = self.format_object(dataship)
                else:
                    variable_value = self.get_nested_attr(dataship, variable_name)

                if format_specifier:
                    variable_value = f"{variable_value:{format_specifier}}"
                elif special_format_specifier:
                    variable_value = self.special_format_specifier(variable_value, special_format_specifier, dataship)
                elif isinstance(variable_value, (str, int, float, tuple, dict)):
                    variable_value = f"{variable_value}"
                elif isinstance(variable_value, list):
                    final_value = ""
                    for item in variable_value:
                        final_value += f"\n{self.format_object(item)}\n======================="
                    variable_value = final_value
                elif isinstance(variable_value, object):
                    variable_value = self.format_object(variable_value)
                else:
                    variable_value = str(variable_value)
            except Exception as e:
                variable_value = f"Err:{str(e)}"

            result = result[:open_brace] + variable_value + result[close_brace + 1:]
            start = open_brace + len(variable_value)

        return result

    def get_data_field(self, dataship, data_field, default_value=0, default_value_on_error=0):
        """
        Get a data field from the dataship object.
        Useful for passing in object string name and getting back the value.
        """
        def get_nested_attr(obj, attr):
            parts = attr.split('.')
            for part in parts:
                # check if its a list if it ends with ]. example: listname[1]
                if part.endswith(']'):
                    index = part[1:-1]
                    # remove the beginning of the string until the first [
                    index = index[index.find('[')+1:]
                    # get the name of the object (from part) example: gpsData
                    name = part[:part.find('[')]
                    # get the value
                    obj = getattr(obj, name)[int(index)]
                elif part.endswith('()'):
                    # It's a function call
                    func_name = part[:-2]
                    obj = getattr(obj, func_name)()
                else:
                    obj = getattr(obj, part)
            return obj
        if data_field == "":
            return default_value
        try:
            return get_nested_attr(dataship, data_field)
        except Exception as e:
            print(f"Error getting data field {data_field}: {e}")
            return default_value_on_error

# vi: modeline tabstop=8 expandtab shiftwidth=4 softtabstop=4 syntax=python
