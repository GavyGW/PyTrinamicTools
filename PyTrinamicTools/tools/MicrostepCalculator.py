#!/usr/bin/env python3
'''
Calculate a modulated microstep table and optionally write it to a TMC5041 IC.

The basis for calculating the default microstep table is a sine wave. A total of
256 values are sampled from the first quarter wave and then encoded into the
microstep table format. By default the sampling is done at equidistant points.

In order to compensate for low quality motors a modulation technique is used.
The sampling points are moved, similar to a longitudal wave. The result is a
modulation of the velocity. The strength of that modulation depends on the
MODULATION_AMPLITUDE parameter.

This script allows implementing your own modulation techniques easily. You can
simply add hardcoded sampling point values or you can implement a generator to
dynamically calculate sampling points.

Created on 22.07.2019

@author: LH
'''

import matplotlib.pyplot as plot
import PyTrinamic
import math
from PyTrinamic.connections.serial_tmcl_interface import serial_tmcl_interface
from PyTrinamic.evalboards.TMC5041_eval import TMC5041_eval
from PyTrinamicTools.helpers.Microsteps import MicroStepTable 

### Parameters #################################################################
# Parameters for the sine wave used in generating the steps
MICROSTEP_AMPLITUDE  = 248
MICROSTEP_OFFSET     = -1

# Amplitude of the modulating sine wave.
# Negative amplitudes result in slower movement around the fullsteps
MODULATION_AMPLITUDE = -27

# Control whether the script uploads the calculated table
UPLOAD_TABLE         = False
################################################################################

def sineWave(amplitude, offset, sampling_points=range(0, 256)):
    '''
    Calculate the sine wave values for microstep encoding.

    Arguments:
        - amplitude:
            The amplitude of the sine wave. Has to be between 0 and 248
        - offset:
            Offset of the sine wave.
        - sampling_points:
            An iterable (e.g. a list) holding the 256 positions where the sine
            wave will be sampled. The values are scaled with:
                radian = (i+0.5)/1024 * 2pi
            This way an input of [0, 255] results in the first quarter sine wave.

    Returns 256 sampled points of the sine wave as a list
    '''
    if not(type(amplitude) == type(offset) == int):
        raise TypeError

    values = []

    for i in sampling_points:
        values += [round(math.sin(2*(i+0.5)/1024*math.pi)*amplitude + offset)]

    if max(values) >= 256:
        raise ValueError("Sampled amplitude has to be below 256")

    if max(values) > 247:
        print("Warning: The amplitude is exceeding 247. This may result in an overflow when combined with SpreadCycle")
    
    if len(values) != 256:
        raise RuntimeError("256 sampling points are required")

    return values

### Generators #################################################################
# Default mechanism: equidistant sampling points
# This generator gives the values from 0 to 255, similar to range(0, 256)
def linearGenerator():
    value = 0
    while value < 256:
        yield value
        value += 1

# Implementation of the equidistant sampling points as a hardcoded list
# This is just a reference on how to manually define sampling points in
# a generator expression.
def hardcodedGenerator():
    values = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 145, 146, 147, 148, 149, 150, 151, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172, 173, 174, 175, 176, 177, 178, 179, 180, 181, 182, 183, 184, 185, 186, 187, 188, 189, 190, 191, 192, 193, 194, 195, 196, 197, 198, 199, 200, 201, 202, 203, 204, 205, 206, 207, 208, 209, 210, 211, 212, 213, 214, 215, 216, 217, 218, 219, 220, 221, 222, 223, 224, 225, 226, 227, 228, 229, 230, 231, 232, 233, 234, 235, 236, 237, 238, 239, 240, 241, 242, 243, 244, 245, 246, 247, 248, 249, 250, 251, 252, 253, 254, 255]
    yield from values

# Sine modulated sampling points
def longitualWaveGenerator(amplitude):
    value = 0
    while value < 256:
        yield value + amplitude*math.sin(2*(value/256)*math.pi)
        value += 1

### main #######################################################################
if __name__ == "__main__":
    # Generate the sampling points
    # You may switch to a different generator here
    sampling_points = list(longitualWaveGenerator(amplitude=MODULATION_AMPLITUDE))
    #sampling_points = list(linearGenerator())
    #sampling_points = list(hardcodedGenerator())

    # Calculate the sine wave
    values = sineWave(MICROSTEP_AMPLITUDE, MICROSTEP_OFFSET, sampling_points)

    # Encode the sine wave into the microstep table format
    try:
        table = MicroStepTable.encodeWaveform(values)
    except ValueError:
        print("Specified waveform could not be encoded")
        table = None

    # Plot the modulation curve
    plot.figure(clear=True)
    plot.plot(sampling_points)
    plot.plot(list(range(0, 256)), '--')
    plot.title("Step modulation")
    plot.show(block= (table==None))

    # If the encoding failed, abort here
    if not(table):
        exit(1)

    # Display register values and plots of the waveforms
    table.printRegisters()
    table.plotQuarterWave(block=False)
    table.plotWaveform(block=True)

    if not(UPLOAD_TABLE):
        exit(0)

    # Upload the table to a TMC5041 connected over USB
    myInterface = serial_tmcl_interface(PyTrinamic.firstAvailableComPort(USB=True))
    TMC5041 = TMC5041_eval(myInterface)

    TMC5041.writeRegister(TMC5041.registers.MSLUT0, table._reg_MSLUT[0])
    TMC5041.writeRegister(TMC5041.registers.MSLUT1, table._reg_MSLUT[1])
    TMC5041.writeRegister(TMC5041.registers.MSLUT2, table._reg_MSLUT[2])
    TMC5041.writeRegister(TMC5041.registers.MSLUT3, table._reg_MSLUT[3])
    TMC5041.writeRegister(TMC5041.registers.MSLUT4, table._reg_MSLUT[4])
    TMC5041.writeRegister(TMC5041.registers.MSLUT5, table._reg_MSLUT[5])
    TMC5041.writeRegister(TMC5041.registers.MSLUT6, table._reg_MSLUT[6])
    TMC5041.writeRegister(TMC5041.registers.MSLUT7, table._reg_MSLUT[7])

    TMC5041.writeRegister(TMC5041.registers.MSLUTSEL, table._reg_MSLUTSEL)
    TMC5041.writeRegister(TMC5041.registers.MSLUTSTART, table._reg_MSLUTSTART)

    myInterface.close()