#!/usr/bin/env python3
'''
Calculate a microstep table and optionally write it to a TMC5041 IC.

Supported waveforms are a sine wave and a trapezoidal wave.
A total of 256 values are sampled and then encoded into the microstep table
format. These 256 values are mirrored in hardware to expand to a total of 1024
values. By default the sampling is done at equidistant points.

In order to compensate for low quality motors a speed modulation technique is
used. The sampling points are moved, similar to a longitudal wave. The result is
a modulation of the velocity. The strength of that modulation depends on the
MODULATION_AMPLITUDE parameter.

For the speed modulation you can hardcode your sampling points.

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

### Speed modulation ###
# Type of speed modulation
# 0: No modulation
# 1: longitudinal modulation
# 2: hardcoded modulation values
MODULATION_TYPE = 1

# Amplitude of the longitudinal modulation sine wave.
# Used when MODULATION_TYPE is 1
# Negative amplitudes result in slower movement around the fullsteps
MODULATION_AMPLITUDE = -27

# Hardcoded modulation values.
# Used when MODULATION_TYPE is 2
MODULATION_VALUES = [
    0,   1,   2,   3,   4,   5,   6,   7,   8,   9,   10,  11,  12,  13,  14,  15,
    16,  17,  18,  19,  20,  21,  22,  23,  24,  25,  26,  27,  28,  29,  30,  31,
    32,  33,  34,  35,  36,  37,  38,  39,  40,  41,  42,  43,  44,  45,  46,  47,
    48,  49,  50,  51,  52,  53,  54,  55,  56,  57,  58,  59,  60,  61,  62,  63,
    64,  65,  66,  67,  68,  69,  70,  71,  72,  73,  74,  75,  76,  77,  78,  79,
    80,  81,  82,  83,  84,  85,  86,  87,  88,  89,  90,  91,  92,  93,  94,  95,
    96,  97,  98,  99,  100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111,
    112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127,
    128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143,
    144, 145, 146, 147, 148, 149, 150, 151, 152, 153, 154, 155, 156, 157, 158, 159,
    160, 161, 162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172, 173, 174, 175,
    176, 177, 178, 179, 180, 181, 182, 183, 184, 185, 186, 187, 188, 189, 190, 191,
    192, 193, 194, 195, 196, 197, 198, 199, 200, 201, 202, 203, 204, 205, 206, 207,
    208, 209, 210, 211, 212, 213, 214, 215, 216, 217, 218, 219, 220, 221, 222, 223,
    224, 225, 226, 227, 228, 229, 230, 231, 232, 233, 234, 235, 236, 237, 238, 239,
    240, 241, 242, 243, 244, 245, 246, 247, 248, 249, 250, 251, 252, 253, 254, 255
    ]

### Waveform configuration ###
# Select the waveform type to be generated
# 0: Sine
# 1: Trapezoidal
WAVEFORM_TYPE = 1

# Parameters for the sine wave
MICROSTEP_SINE_AMPLITUDE  = 248
MICROSTEP_SINE_OFFSET     = -1

# Parameters for the trapezoidal wave
MICROSTEP_TRAPEZOIDAL_GRADIENT = 1
MICROSTEP_TRAPEZOIDAL_OFFSET   = 0
MICROSTEP_TRAPEZOIDAL_LIMIT    = 247

# Control whether the script uploads the calculated table to the TMC5041
UPLOAD_TABLE = False

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

    Returns 256 sampled points of the sine wave as a list of integers
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

def trapezoidalWave(gradient, limit, offset, sampling_points=range(0, 256)):
    '''
    Calculate the trapezoidal wave values for microstep encoding.

    Arguments:
        - gradient:
            The gradient of the curve. Permitted values: 0 < gradient <= 3
            If this value is not an integer, the step values will be rounded
            for each step.
        - offset:
            The offset of the curve. If the offset is negative any values below
            0 will be clipped to 0.
        - limit:
            The maximum value after which the gradient line stops and a
            horizontal line continues. This value must be below 256 and should
            be below 248 (for SpreadCycle operation).
        - sampling_points:
            An iterable (e.g. a list) holding the 256 positions where the gradient
            will be sampled.

    Returns 256 sampled points of a trapezoidal waveform as a list of integers
    '''
    if not (0 < gradient <= 3):
        raise ValueError("Invalid gradient value")

    values = []

    for i in sampling_points:
        # Calculate the desired value (not rounded yet)
        desired_value = (i * gradient) - offset
        # Limit the value to [0, limit]
        desired_value = desired_value if desired_value >= 0 else 0
        desired_value = desired_value if desired_value < limit else limit
        # Round the value and add it to the list
        values += [round(desired_value)]

    if max(values) >= 256:
        raise ValueError("Sampled amplitude has to be below 256")

    if max(values) > 247:
        print("Warning: The amplitude is exceeding 247. This may result in an overflow when combined with SpreadCycle")

    if len(values) != 256:
        raise ValueError("256 sampling points are required")

    return values

### Speed modulation ###########################################################
### For modulating the speed along the waveform, values between 0 and 256 are
### required. Unmodulated speed is represented by the values 0, 1, ... 254, 255.
### These values represent X values in the graph of the used waveform. The
### resulting Y values are then encoded as microsteps.
###
### This implementation uses python generator expressions to represent the 256
### needed values.

# Default mechanism: equidistant sampling points
# This generator gives the values from 0 to 255, similar to range(0, 256)
def linearGenerator():
    value = 0
    while value < 256:
        yield value
        value += 1

# Implementation of hardcoded sampling points. By default the values in the
# hardcoded list are equal to the linearGenerator() values: 0 to 255.
def hardcodedGenerator():
    values = MODULATION_VALUES
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
    if MODULATION_TYPE == 0:
        sampling_points = list(linearGenerator())
    elif MODULATION_TYPE == 1:
        sampling_points = list(longitualWaveGenerator(amplitude=MODULATION_AMPLITUDE))
    elif MODULATION_TYPE == 2:
        sampling_points = list(hardcodedGenerator())
    else:
        raise ValueError("Invalid MODULATION_TYPE selected")

    if WAVEFORM_TYPE == 0:
        # Calculate a sine wave
        values = sineWave(MICROSTEP_SINE_AMPLITUDE, MICROSTEP_SINE_OFFSET, sampling_points)
    elif WAVEFORM_TYPE == 1:
        # Calculate a trapezoidal wave
        values = trapezoidalWave(MICROSTEP_TRAPEZOIDAL_GRADIENT, MICROSTEP_TRAPEZOIDAL_LIMIT, MICROSTEP_TRAPEZOIDAL_OFFSET, sampling_points)
    else:
        raise ValueError("Invalid WAVEFORM_TYPE selected")

    # Encode the waveform into the microstep table format
    try:
        table = MicroStepTable.encodeWaveform(values)
    except ValueError as e:
        print("Specified waveform could not be encoded: " + str(e))
        table = None

    if MODULATION_TYPE != 0:
        # Plot the modulation curve
        plot.figure(clear=True)
        plot.plot(sampling_points)
        plot.plot(list(range(0, 256)), '--')
        plot.plot(sampling_points[0::4], [0]*64, 'x')
        plot.title("Step modulation")
        plot.show(block= (table==None))

    # If the encoding failed, abort here
    if not(table):
        exit(1)

    # Display register values and plots of the waveforms
    table.printRegisters()
    table.plotQuarterWave(block=False)
    table.plotXY(block=False)
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
