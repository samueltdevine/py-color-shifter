"""
Copyright: MAXON Computer GmbH
Author: SD

Description:
    - Creates a Dialog to manage texture baking.
    - Bakes selected object diffuse to the uv and display the result in the Picture Viewer.

Class/method highlighted:
    - c4d.threading.C4DThread
    - C4DThread.Main()
    - c4d.gui.GeDialog
    - GeDialog.CreateLayout()
    - GeDialog.Command()
    - GeDialog.CoreMessage()
    - GeDialog.AskClose()
    - c4d.plugins.CommandData
    - CommandData.Execute()
    - CommandData.RestoreLayout()

"""
from contextlib import nullcontext
from importlib.resources import read_binary
from mimetypes import init
import c4d
try:
    from RedshiftWrapper.Redshift import Redshift
except:
    raise RuntimeError("Could not import Redshift.")
    

# Be sure to use a unique ID obtained from www.plugincafe.com
PLUGIN_ID = 1060022
redshift = Redshift()
colors = []
expectedColors = []
targetColors = []
YOUR_IDENT = 49545
readpath = None
writepath = None

class ColorShifterThread(c4d.threading.C4DThread):
    """Cinema 4D Thread for the ColorShifter Command Plugin"""

    def __init__(self, doc, textags, texuvws, destuvws):
        """Initializes the Texture Baker thread.

        Args:
            doc (c4d.documents.BaseDocument): the document hosting the object.
            textags (c4d.TextureTag): List of the texture tag(s) to bake. Must be assigned to an object.
            texuvws (c4d.UVWTag): The UVW tag(s) to bake.
            destuvws (c4d.UVWTag): The destination UVW tag for the bake.
        """
        self.doc = doc
        self.textags = textags
        self.texuvws = texuvws
        self.destuvws = destuvws

        self.bakeDoc = None
        self.bakeData = None
        self.bakeBmp = c4d.bitmaps.MultipassBitmap(512, 512, c4d.COLORMODE_RGB)
        self.bakeError = c4d.BAKE_TEX_ERR_NONE


class ColorShifterHelper(object):

    def EnableButtons(self, baking):
        """Defines the state of the button according of the baking process.

        Args:
            baking: Current baking state (True if baking occurs)
        """
        self.Enable(self.BUTTON_BAKE, not baking)
        self.Enable(self.BUTTON_ABORT, baking)

    def Get(self):
        """gets all colors"""
        doc = c4d.documents.GetActiveDocument()
        materialList = doc.GetMaterials()
        # print(materialList)
        # mat = materialList[0]
        expectedColor = c4d.Vector(0, 0, 1)
        targetColor = c4d.Vector(1, 1, 1)
        #for mat in materialList:
        #print(mat[c4d.MATERIAL_COLOR_COLOR])
        colors.clear()

        for mat in materialList:
            master = redshift.GetRSMaterialNodeMaster(mat)
            print(master)
            existingColor = mat[c4d.REDSHIFT_SHADER_MATERIAL_DIFFUSE_COLOR]
            colors.append(existingColor)
            #if existingColor == expectedColor:
                #mat[c4d.MATERIAL_COLOR_COLOR] = targetColor
        # print(materialList)
        # print(colors)

    def Convert(self):
        doc = c4d.documents.GetActiveDocument()
        materialList = doc.GetMaterials()

        for i, mat in enumerate(materialList):
             existingColor = mat[c4d.REDSHIFT_SHADER_MATERIAL_DIFFUSE_COLOR]
             for e, expectedColor in enumerate(expectedColors):
                if existingColor == expectedColor:
                    mat[c4d.REDSHIFT_SHADER_MATERIAL_DIFFUSE_COLOR] = targetColors[e]
        # for i, mat in enumerate(materialList):
        #     existingColor = mat[c4d.MATERIAL_COLOR_COLOR]
        #     if expectedColors[i] == existingColor:
        #         mat[c4d.MATERIAL_COLOR_COLOR] = targetColors[i]

    
    def Write(path, key):
        #write
        print(path)
        hf = c4d.storage.HyperFile()
        if hf.Open(ident=key, filename=path, mode=c4d.FILEOPEN_WRITE, error_dialog=c4d.FILEDIALOG_NONE):
            bc = c4d.BaseContainer()
            bc[0] = expectedColors
            bc[1] = targetColors
            hf.WriteContainer(bc)
            hf.Close()
        else:
            c4d.gui.MessageDialog("Cannot open file to write.")

    def Read(path, key):
        #read
        hf = c4d.storage.HyperFile()
        if hf.Open(ident=key, filename=path, mode=c4d.FILEOPEN_READ, error_dialog=c4d.FILEDIALOG_NONE):
            bc = hf.ReadContainer()
            hf.Close()
            expectedColors = bc[0]
            targetColors = bc[1] #output: test 3
        else:
            c4d.gui.MessageDialog("Cannot open file to read.")

#    Write(path, YOUR_IDENT)
#    Read(path, YOUR_IDENT)

class ColorShifterDlg(c4d.gui.GeDialog, ColorShifterHelper):
    """Main dialog for the Texture Baker"""
    BUTTON_GET = 1002
    BUTTON_CONVERT = 1003
    BUTTON_BAKE = 1000
    BUTTON_ABORT = 1001
    ID_PALLETTE = 2001
    ID_MAIN = 3000
    ID_SAVE_LOAD = 4000
    BUTTON_SAVE = 4001
    BUTTON_LOAD = 4002
    PATH_SAVE = 4003
    PATH_LOAD = 4004
    PATH_SAVE_STR = 4005
    PATH_LOAD_STR = 4006

    aborted = False
    ColorShifterThread = None
    infoText = None

    def InitValues(self):
        self.SetString(self.PATH_SAVE, "Save File Path", flags=c4d.EDITTEXT_HELPTEXT)
        self.SetString(self.PATH_LOAD, "Load File Path", flags=c4d.EDITTEXT_HELPTEXT)

    def CreateLayout(self):
        """This Method is called automatically when Cinema 4D Create the Layout (display) of the Dialog."""
        # Defines the title
        self.SetTitle("Color Pallette Switcher")
        self.MenuFlushAll()
        # self.LayoutFlushGroup(2001)

        self.GroupBegin(id=3000, flags=c4d.BFH_SCALEFIT, cols=2, rows= 1, title="Get and Convert", groupflags=0)
        # Creates 2 buttons for Bake / Abort button
        self.AddButton(id=self.BUTTON_GET, flags=c4d.BFH_LEFT, initw=100, inith=25, name="Get Colors")
        self.AddButton(id=self.BUTTON_CONVERT, flags=c4d.BFH_RIGHT, initw=100, inith=25, name="Convert Colors")

        self.GroupEnd()
        self.AddEditText(id=self.PATH_SAVE, flags=c4d.BFH_LEFT, initw=300, inith=10, editflags=c4d.EDITTEXT_HELPTEXT)
        self.AddEditText(id=self.PATH_LOAD, flags=c4d.BFH_LEFT, initw=300, inith=10,editflags=c4d.EDITTEXT_HELPTEXT)

        self.GroupBegin(id=self.ID_SAVE_LOAD, flags=c4d.BFH_SCALEFIT, cols=2, rows= 1, title="Save and Load", groupflags=0)

        self.AddButton(id=self.BUTTON_SAVE, flags=c4d.BFH_LEFT, initw=100, inith=25, name="Save")
        self.AddButton(id=self.BUTTON_LOAD, flags=c4d.BFH_RIGHT, initw=100, inith=25, name="Load")
        self.GroupEnd()
        self.GroupBegin(id=2001, flags=c4d.BFH_SCALEFIT, cols=2, rows= 1, title="", groupflags=0)

        self.GroupEnd()
        
        # Creates a statics text for the status

        # Sets Button enable states so only bake button can be pressed
        self.EnableButtons(False)

       


        return True

   
    

    def Command(self, id, msg):
        """This Method is called automatically when the user clicks on a gadget and/or changes its value this function will be called.
        It is also called when a string menu item is selected.

        Args:
            id (int): The ID of the gadget that triggered the event.
            msg (c4d.BaseContainer): The original message container

        Returns:
            bool: False if there was an error, otherwise True.
        """
        if id == self.BUTTON_SAVE:
            self.Write(writepath, YOUR_IDENT)

        if id == self.BUTTON_SAVE:
            self.Read(readpath, YOUR_IDENT)

        if id == self.BUTTON_GET:
            self.Get()
            # self.LayoutFlushGroup(2001)
            # self.GroupBegin(id=4000, flags=c4d.BFH_SCALEFIT, cols=2, rows= 1, title="Swatches", groupflags=0)
            # for idx, color in enumerate(colors):
            #     self.AddColorField(id=9000+idx ,flags=c4d.BFH_LEFT, initw=0, inith=20, colorflags=0)
            #     self.AddColorField(id=8000+idx ,flags=c4d.BFH_RIGHT, initw=0, inith=20, colorflags=0)
            #     self.SetColorField(id=9000+idx , color=color, brightness=100, maxbrightness=100, flags=0)
            # self.LayoutChanged(2001)
            self.GroupEnd()

        
        if id == self.PATH_SAVE:
            readpath = self.GetString(self.PATH_SAVE)
            #print(writepath)
        
        if id == self.PATH_LOAD:
            readpath = self.GetString(self.PATH_LOAD)
            #print(readpath)
        
        if id == self.BUTTON_CONVERT:
            colorAmt = len(colors)
            targetColors.clear()
            expectedColors.clear()
            for idx, color in enumerate(colors):
                ID=8000+idx
                color = self.GetColorField(ID)["color"]
                targetColors.append(color)
            
            for idx, color in enumerate(colors):
                ID=9000+idx
                color = self.GetColorField(ID)["color"]
                expectedColors.append(color)


            # print(self.GetColorField(ID))
            self.Convert()
        return True

    def CoreMessage(self, id, msg):
        """This Method is called automatically when Core (Main) Message is received.

        Args:
            id (int): The ID of the gadget that triggered the event.
            msg (c4d.BaseContainer): The original message container

        Returns:
            bool: False if there was an error, otherwise True.
        """
        # Checks if texture baking has finished
        if id == PLUGIN_ID:
            # Sets Button enable states so only bake button can be pressed
            self.EnableButtons(False)

            # If not aborted, means the baking finished
            if not self.aborted:
                # Updates the information status
                self.SetString(self.infoText, str("Baking Finished"))

                # Retrieves the baked bitmap
                bmp = self.ColorShifterThread.bakeBmp
                if bmp is None:
                    raise RuntimeError("Failed to retrieve the baked bitmap.")

                # Displays the bitmap
                c4d.bitmaps.ShowBitmap(bmp)

                # Removes the reference to the C4D Thread, so the memory used is free
                self.ColorShifterThread = None
                return True
            else:
                # If baking is aborted, updates the information status
                self.SetString(self.infoText, str("Baking Aborted"))

            return True

        return c4d.gui.GeDialog.CoreMessage(self, id, msg)

    def AskClose(self):
        """This Method is called automatically when self.Close() is called or the user press the Close cross in top menu.

        Returns:
            bool: True if the Dialog shouldn't close, otherwise False.
        """
        # Aborts the baking process on dialog close
        self.Abort()
        return False


class ColorShifterData(c4d.plugins.CommandData):
    """Command Data class that holds the ColorShifterDlg instance."""
    dialog = None

    def Execute(self, doc):
        """Called when the user Execute the command (CallCommand or a clicks on the Command from the plugin menu)

        Args:
            doc (c4d.documents.BaseDocument): the current active document

        Returns:
            bool: True if the command success
        """
        # Creates the dialog if its not already exists
        if self.dialog is None:
            self.dialog = ColorShifterDlg()

        # Opens the dialog
        return self.dialog.Open(dlgtype=c4d.DLG_TYPE_ASYNC, pluginid=PLUGIN_ID, defaultw=250, defaulth=50)

    def RestoreLayout(self, sec_ref):
        """Used to restore an asynchronous dialog that has been placed in the users layout.

        Args:
            sec_ref (PyCObject): The data that needs to be passed to the dlg (almost no use of it).

        Returns:
            bool: True if the restore success
        """
    
        # Creates the dialog if its not already exists
        if self.dialog is None:
            self.dialog = ColorShifterDlg()

        # Restores the layout
        return self.dialog.Restore(pluginid=PLUGIN_ID, secret=sec_ref)


if __name__ == "__main__":
    c4d.plugins.RegisterCommandPlugin(id=PLUGIN_ID, str="Py-ColorShifter",
                                  help="Py - Color Shifter", info=0,
                                  dat=ColorShifterData(), icon=None)
