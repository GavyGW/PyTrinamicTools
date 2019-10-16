'''
This file provides the MicroStepTable class for using the microstep table encoding

Created: 18.07.2019

@author: LH
'''

import matplotlib.pyplot as plot
import math
from PyTrinamic.helpers import TMC_helpers

class MicroStepTable():
    '''
    This class holds the values for one microstep table.

    The table may be initialized either with already encoded registers or with a
    sine waveform using the factory methods decodeRegisters() and
    encodeWaveform() respectively.

    Once the table is initialized it can be printed out or plotted with various
    helper functions.
    '''
    def __init__(self):
        self._initialized = False
        
        # Storage for waveform
        self._waveform = None
        
        # Storage for registers
        self._reg_MSLUT      = None
        self._reg_MSLUTSEL   = None
        self._reg_MSLUTSTART = None
    
    @classmethod
    def encodeWaveform(cls, waveform):
        obj = cls()
        # Verify the waveform parameter
        if not(type(waveform) == list):
            raise TypeError
        if not(len(waveform) == 256):
            raise ValueError("Waveform does not have 256 entries")
        if max(waveform) > 255:
            raise ValueError("Waveform is surpassing the maximum value of 255")
        if min(waveform) < -256:
            raise ValueError("Waveform is surpassing the minimum value of -256")
        
        # Calculate the waveform for storage
        obj._waveform = []
        # Expand the quarter sine wave to the half sine wave
        waveform += list(reversed(waveform))
        # Expand the half sine wave to the full sinewave
        offset = 2*waveform[0] - 1
        waveform += [-x+offset for x in reversed(waveform)]
        # Calculate the cosine wave and store both waves as a list of tuples
        # Tuple format: (index, sine, cosine)
        for i in range(0, len(waveform)):
            obj._waveform += [ (i, waveform[i], waveform[(i+256)%1024]) ]
        
        # Calculate the differences between adjacent waveform values
        difference = []
        for i in range(1, 256):
            difference = difference + [waveform[i] - waveform[i-1]]
        
        # Find all the different sections
        minDiff = maxDiff = difference[0]
        sections = []
        for i, val in enumerate(difference):
            if val > minDiff + 1:
                # Newest value is too high for current section
                # -> Start a new section
                sections = sections + [(i, minDiff)]
                
                minDiff = maxDiff = val
                
            if val < maxDiff - 1:
                # Newest value is too low for current section
                # -> Start a new section
                sections = sections + [(i, minDiff)]
                
                minDiff = maxDiff = val
    
            # Update Max/Min values
            maxDiff = max(maxDiff, val)
            minDiff = min(minDiff, val)
    
        # Add the final section
        sections = sections + [(i, minDiff)]

        # Encoding check: Only 4 sections are allowed
        if (len(sections) > 4):
            raise ValueError("More than 4 sections are required to represent this waveform")
        # If less than 4 sections are required, fill the list with dummy sections
        while len(sections) < 4:
            sections = sections + [(255, 0)]

        # Encoding check: Section offsets must be between -1 and 2
        for i, section in enumerate(sections):
            if not( -1 <= section[1] <= 2 ):
                raise ValueError("Waveform is too steep. (Section {0} requires an illegal base offset of {1})".format(i, section[1]))
        
        # Add a 256th dummy value to the difference list (at the start)
        difference = [0] + difference
        
        # Subtract all the offset values from the difference values
        # This yields the offset bits to be encoded in the MSLUT registers
        for i, val in enumerate(difference, 1):
            for j in range(0, len(sections)):
                if i < sections[j][0]:
                    difference[i] -= sections[j][1]
                    break
        
        # Sanity check: bit values should only contain zeroes and ones
        # This should never happen unless the calculation above is buggy
        if min(difference) < 0 or max(difference) > 1:
            raise RuntimeError("Something went wrong with the conversion to MSLUT bits")
        
        # Fill the MSLUT bitfields
        obj._reg_MSLUT = 8*[0]
        for i in range(0, 256):
            obj._reg_MSLUT[math.floor(i/32) & 7] |= difference[i] << (i%32)
        
        # Determine the START_SIN and START_SIN90 values
        startSin = waveform[0]
        startCos = waveform[256]
        
        # Fill the MSLUTSEL register
        obj._reg_MSLUTSEL = sections[2][0] << 24 | sections[1][0] << 16 | sections[0][0] << 8 | (sections[3][1] + 1) << 6 | (sections[2][1] + 1) << 4 | (sections[1][1] + 1) << 2 | (sections[0][1] + 1)
    
        # Fill the MSLUTSTART register
        obj._reg_MSLUTSTART = startCos << 16 | startSin
        
        # The table is now initialized
        obj._initialized = True
        
        return obj
    
    @classmethod
    def decodeRegisters(cls, MSLUT, MSLUTSEL, MSLUTSTART):
        obj = cls()
        
        obj._reg_MSLUT       = MSLUT
        obj._reg_MSLUTSEL    = MSLUTSEL
        obj._reg_MSLUTSTART  = MSLUTSTART
        
        ranges = [
            (TMC_helpers.field_get(MSLUTSEL, 0x0000FF00,  8), TMC_helpers.field_get(MSLUTSEL, 0x00000003, 0)),
            (TMC_helpers.field_get(MSLUTSEL, 0x00FF0000, 16), TMC_helpers.field_get(MSLUTSEL, 0x0000000C, 2)),
            (TMC_helpers.field_get(MSLUTSEL, 0xFF000000, 24), TMC_helpers.field_get(MSLUTSEL, 0x00000030, 4)),
            (255,                                             TMC_helpers.field_get(MSLUTSEL, 0x000000C0, 6)),
        ]
        
        if not(ranges[0][0] <= ranges[1][0] <= ranges[2][0] <= ranges[3][0]):
            raise ValueError("Condition X1 <= X2 <= X3 <= X4 not satisfied")
        
        startSin = TMC_helpers.field_get(MSLUTSTART, 0x000000FF,  0)
        startCos = TMC_helpers.field_get(MSLUTSTART, 0x00FF0000, 16)
        
        # Generate the first quarter sine wave
        sineValues = [ (0, startSin) ]
        for i in range(1, 257):
            for j in range(0, 4):
                if i < ranges[j][0]:
                    offset = ranges[j][1] - 1
                    break
        
            bitValue   = ((MSLUT[math.floor((i)/32) & 7] >> ((i) % 32) ) & 1)
            deltaValue = bitValue + offset
            newValue   = sineValues[i-1][1] + deltaValue
            sineValues += [(i, newValue)]
        
        # Generate the second quarter sine wave
        for i in range(257, 512):
            newValue = sineValues[511-i][1]
            sineValues += [(i, newValue)]
        
        # Generate the remaining sine wave
        offset = 2*sineValues[0][1] - 1
        for i in range(512, 1024):
            newValue = -sineValues[i-512][1] + offset
            sineValues += [(i, newValue)]
        
        # Generate the cosine wave
        cosOffset = startCos - sineValues[256][1]
        obj._waveform = []
        for i in range(0, 1024):
            tmp = sineValues[i]
            obj._waveform += [(tmp[0], tmp[1], sineValues[(i+256) % 1024][1] + cosOffset)]
     
        # The table is now initialized
        obj._initialized = True
        
        return obj
    
    def getWaveform(self):
        if not(self._initialized):
            raise RuntimeError("Table is not initialized")
        
        return self._waveform
    
    def getSineWave(self):
        if not(self._initialized):
            raise RuntimeError("Table is not initialized")
        
        return [x[1] for x in self._waveform]
    
    def getCosineWave(self):
        if not(self._initialized):
            raise RuntimeError("Table is not initialized")
        
        return [x[2] for x in self._waveform]
    
    def getRegisters(self):
        if not(self._initialized):
            raise RuntimeError("Table is not initialized")
        
        return (self._reg_MSLUT, self._reg_MSLUTSEL, self._reg_MSLUTSTART)
    
    def printRegisters(self):
        if not(self._initialized):
            raise RuntimeError("Table is not initialized")
        
        for i, r in enumerate(self._reg_MSLUT, 0):
            print("MSLUT[{0:d}]:    0x{1:08X}".format(i, r))
        print("MSLUTSEL:    0x{0:08X}".format(self._reg_MSLUTSEL))
        print("MSLUTSTART:  0x{0:08X}".format(self._reg_MSLUTSTART))
        print()
    
    def plotWaveform(self, block=True):
        plot.figure()
        plot.plot([(x[1], x[2]) for x in self._waveform])
        plot.title("Microstep table waveform")
        plot.show(block=block)

    def plotQuarterWave(self, block=True):
        plot.figure()
        plot.plot([(x[1]) for x in self._waveform[0:256]])
        plot.title("Microstep quarter sine wave")
        plot.show(block=block)
    
    def plotXY(self, block=True):
        plot.figure()
        plot.plot([x[1] for x in self._waveform], [x[2] for x in self._waveform])
        plot.show(block=block)

if __name__ == "__main__":
    # Default MSLUT register values
    MSLUT = [
        0xAAAAB554,
        0x4A9554AA,
        0x24492929,
        0x10104222,
        0xFBFFFFFF,
        0xB5BB777D,
        0x49295556,
        0x00404222
    ]
    MSLUTSEL   = 0xFFFF8056
    MSLUTSTART = 0x00F70000
    MSLUTSTART = 0x00F70000
    
    # Decode the default table
    myTable1 = MicroStepTable.decodeRegisters(MSLUT, MSLUTSEL, MSLUTSTART)
    
    # Encode the first quarter of the sine wave to MSLUT registers
    myTable2 = MicroStepTable.encodeWaveform(myTable1.getSineWave()[0:256])
    
    # Print the registers of both tables. Note that the encoding allows the same
    # waveform to be encoded in multiple ways - the registers may differ.
    print("Table 1:")
    myTable1.printRegisters()
    print("Table 2:")
    myTable2.printRegisters()
    
    # Verification: Compare both tables
    waveform1 = myTable1.getWaveform()
    waveform2 = myTable2.getWaveform()
    
    for i in range(0, len(waveform1)):
        if waveform1[i][1] != waveform2[i][1]:
            print("Error on step {0:3d}: old={1:d}, new={2:d}".format(i, waveform1[i][1], waveform2[i][1]))
            break
    else:
        print("Encoding correct")
    