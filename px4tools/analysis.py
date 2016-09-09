"""
Analysis of px4 logs
"""

#pylint: disable=invalid-name, missing-docstring, no-member

from __future__ import print_function
import pandas
import pylab as pl
import matplotlib.patches as patches
import six
from matplotlib import colors

try:
    from .mapping import *
except ImportError as e:
    print(e)

FLIGHT_MODES = ['MANUAL', 'ALTCTL', 'POSCTL', 'AUTO_MISSION', 'AUTO_LOITER', 'AUTO_RTL', 'ACRO', 'OFFBOARD', 'STAB', 'RATTITUDE', 'AUTO_TAKEOFF', 'AUTO_LAND', 'AUTO_FOLLOW_TARGET', 'MAX']


def filter_finite(data):

    return pl.all(data[pl.isfinite(data.values.astype(float))], axis=1)

def octa_cox_data_to_ss(data):
    """
    Extracts state space model data from octa cox log.
    """
    t = pandas.Series((data['TIME_StartTime'] -
        data['TIME_StartTime'].values[0])/1.0e6, name='t, sec')
    xh = pandas.DataFrame(data[[
        'LPOS_X', 'LPOS_Y', 'LPOS_Z',
        'LPOS_VX', 'LPOS_VY', 'LPOS_VZ',
        'ATT_Roll', 'ATT_Pitch', 'ATT_Yaw',
        'ATT_RollRate', 'ATT_PitchRate', 'ATT_YawRate']].values,
        columns=['X', 'Y', 'Z', 'V_X', 'V_Y', 'V_Z',
            'Phi', 'Theta', 'Psi',
            'P', 'Q', 'R'], index=t)
    y = pandas.DataFrame(data[[
        'GPS_Lat', 'GPS_Lon', 'GPS_Alt',
        'SENS_BaroAlt',
        'IMU1_AccX', 'IMU1_AccY', 'IMU1_AccZ',
        'IMU1_GyroX', 'IMU1_GyroY', 'IMU1_GyroZ',
        'IMU1_MagX', 'IMU1_MagY', 'IMU1_MagZ']].values,
        columns=['GPS_Lat', 'GPS_Lon', 'GPS_Alt',
            'Baro_Alt',
            'Acc_X', 'Acc_Y', 'Acc_Z',
            'Gyro_X', 'Gyro_Y', 'Gyro_Z',
            'Mag_X', 'Mag_Y', 'Mag_Z'], index=t)
    u_raw = pandas.DataFrame(((
        data[['OUT0_Out0', 'OUT0_Out1', 'OUT0_Out2',
        'OUT0_Out3', 'OUT0_Out4', 'OUT0_Out5', 'OUT0_Out6',
              'OUT0_Out7']] - 1000.0)/1000.0).values,
        columns=['1', '2', '3', '4', '5', '6', '7', '8'], index=t)
    C_mix_octo = pl.array([
                           [1, 1, 1, 1, 1, 1, 1, 1], # thrust
                           [-1, 1, 1, -1, -1, 1, 1, -1], # roll
                           [-1, -1, 1, 1, -1, -1, 1, 1], # pitch
                           [1, -1, 1, -1, 1, -1, 1, -1], # yaw
                          ])/8.0
    u = pandas.DataFrame(C_mix_octo.dot(u_raw.T).T,
            columns=['thrust', 'roll', 'pitch', 'yaw'],
                         index=t)
    return t, xh, u, y, u_raw

def alt_analysis(data, min_alt=None, max_alt=None):
    """
    Altitude analysis.
    """

    i0_Baro = data.SENS_BaroAlt.first_valid_index()
    i0_GPS = data.GPS_Alt.first_valid_index()

    try:
        data.DIST_Distance.plot(legend=True)
    except AttributeError:
        data.DIST_Bottom.plot(legend=True)
    except Exception:
        pass
    (-1*data.LPSP_Z).plot(legend=True)
    (data.SENS_BaroAlt - data.SENS_BaroAlt[i0_Baro]).plot(legend=True)
    (data.GPS_Alt - data.GPS_Alt[i0_GPS]).plot(legend=True)
    (-1*data).LPOS_Z.plot(legend=True)

    if min_alt is not None and max_alt is not None:
        pl.axis([data.index[0], data.index[-1], min_alt, max_alt])
    pl.grid()
    pl.xlabel('t, sec')
    pl.ylabel('altitude, m')
    background_flight_modes(data)

def pos_analysis(data):
    """
    Analyze position.
    """
    tmerc_map = create_map(data.GPS_Lon.values, data.GPS_Lat.values)
    gps_y, gps_x = tmerc_map(data.GPS_Lon.values, data.GPS_Lat.values)
    gpos_y, gpos_x = tmerc_map(data.GPOS_Lon.values, data.GPOS_Lat.values)
    gpsp_y, gpsp_x = tmerc_map(data.GPSP_Lon[
        pl.isfinite(data.GPSP_Lon.values)].values,
        data.GPSP_Lat[pl.isfinite(data.GPSP_Lat.values)].values)

    pl.plot(gpos_y, gpos_x, '.', label='est')

    pl.plot(gps_y, gps_x, 'x', label='GPS')

    pl.plot(gpsp_y, gpsp_x, 'ro', label='cmd')

    pl.xlabel('E, m')
    pl.ylabel('N, m')
    pl.grid()
    pl.autoscale(True, 'both', True)
    pl.legend(loc='best')

def isfloatarray(cell):
    """
    Convert cell to float if possible.
    """
    try:
        cell.astype(float)
        return True
    except ValueError:
        return False

def get_float_data(dataframe):
    """
    Get float data out of dataframe.
    """
    dataframe = dataframe[pl.isfinite(dataframe.TIME_StartTime)]
    float_cols = [isfloatarray(col) for col in dataframe.values.T]
    return (dataframe.T[float_cols].T).astype(float)

def get_auto_data(data):
    """
    Extract auto data.
    """
    data = data[data['STAT_MainState'] == 3]
    data = data[pl.isfinite(data['GPSP_Lat'].astype(float))]
    data = data[pl.isfinite(data['GPSP_Lon'].astype(float))]
    if len(data) == 0:
        raise RuntimeError('no auto mode detected')
    return data

def set_time_series(data):
    """
    Set data to use time series
    """
    t = pandas.Series((data['TIME_StartTime'] -
        data['TIME_StartTime'].values[0])/1.0e6, name='t, sec')
    data = pandas.DataFrame(data.values,
        columns=data.columns, index=t)
    return data

def process_data(data):
    return set_time_series(get_float_data(data))

def plot_attitude_loops(data):
    """
    Plot attitude loops.
    """
    pl.subplot(311)
    pl.title('attitude')
    pl.rad2deg(data.ATT_Roll).plot(legend=True)
    pl.rad2deg(data.ATSP_RollSP).plot()
    pl.ylabel('roll, deg')
    pl.grid(True)
    background_flight_modes(data)

    pl.subplot(312)
    pl.rad2deg(data.ATT_Pitch).plot(legend=True)
    pl.rad2deg(data.ATSP_PitchSP).plot()
    pl.grid(True)
    pl.ylabel('pitch, deg')
    background_flight_modes(data)

    pl.subplot(313)
    pl.rad2deg(data.ATT_Yaw).plot(legend=True)
    pl.rad2deg(data.ATSP_YawSP).plot()
    pl.grid(True)
    pl.ylabel('yaw, deg')
    background_flight_modes(data)


def plot_attitude_rate_loops(data):
    """
    Plot attitude rate control loops.
    """
    pl.title('attitude rate control')

    pl.subplot(311)
    pl.rad2deg(data.ATT_RollRate).plot(legend=True)
    pl.rad2deg(data.ARSP_RollRateSP).plot()
    pl.ylabel('roll, deg/s')
    pl.grid(True)
    background_flight_modes(data)

    pl.subplot(312)
    pl.rad2deg(data.ATT_PitchRate).plot(legend=True)
    pl.rad2deg(data.ARSP_PitchRateSP).plot()
    pl.ylabel('pitch, deg/s')
    pl.grid(True)
    background_flight_modes(data)

    pl.subplot(313)
    pl.rad2deg(data.ATT_YawRate).plot(legend=True)
    pl.rad2deg(data.ARSP_YawRateSP).plot()
    pl.xlabel('t, sec')
    pl.ylabel('yaw, deg/s')
    pl.grid(True)
    background_flight_modes(data)


def plot_attitude_control_loops(data):

    pl.title('attitude control')

    pl.subplot(311)
    pl.rad2deg(data.ATTC_Roll).plot(legend=True)
    pl.ylabel('roll, deg/s')

    pl.subplot(312)
    pl.rad2deg(data.ATTC_Pitch).plot(legend=True)
    pl.ylabel('pitch, deg/s')

    pl.subplot(313)
    pl.rad2deg(data.ATTC_Yaw).plot(legend=True)
    pl.ylabel('yaw, deg/s')

def plot_velocity_loops(data):
    """
    Plot velocity loops.
    """
    pl.subplot(311)
    pl.title('velocity control')
    data.LPOS_VX.plot(legend=True)
    data.LPSP_VX.plot()
    pl.ylabel('x, m/s')
    pl.grid(True)
    background_flight_modes(data)

    pl.subplot(312)
    data.LPOS_VY.plot(legend=True)
    data.LPSP_VY.plot()
    pl.ylabel('y, m/s')
    pl.grid(True)
    background_flight_modes(data)

    pl.subplot(313)
    data.LPOS_VZ.plot(legend=True)
    data.LPSP_VZ.plot()
    pl.xlabel('t, sec')
    pl.ylabel('z, m/s')
    pl.grid(True)
    background_flight_modes(data)

def plot_position_loops(data):
    """
    Plot position loops.
    """
    pl.subplot(311)
    pl.title('position control')
    data.LPOS_X.plot(legend=True)
    data.LPSP_X.plot()
    pl.ylabel('x, m')
    pl.grid(True)
    background_flight_modes(data)

    pl.subplot(312)
    data.LPOS_Y.plot(legend=True)
    data.LPSP_Y.plot()
    pl.ylabel('y, m')
    pl.grid(True)
    background_flight_modes(data)

    pl.subplot(313)
    data.LPOS_Z.plot(legend=True)
    data.LPSP_Z.plot()
    pl.ylabel('z, m')
    pl.grid(True)
    background_flight_modes(data)


def plot_control_loops(data):
    """
    Plot all control loops.
    """
    plot_attitude_rate_loops(data)
    plot_attitude_loops(data)
    plot_velocity_loops(data)
    plot_position_loops(data)

def plot_skip_count_en(data):
    """
    Plot Skip count Enabled.
    """
    print('Skip Count: ' + data.SKC)
    pl.title('Skip Count Enabled')
    pl.ylabel('enabled')
    data.SK.plot(legend=True)
    background_flight_modes(data)


def plot_rc_inputs(data, rc_mapping=None):
    """
    Plot RC Inputs. Optional rc_mapping to reflect channel function in legend.
    """

    pl.title('RC Inputs')
    pl.ylabel('Normalized Inputs (%)')

    (100 * data.RC_C0).plot(legend=True)
    (100 * data.RC_C1).plot(legend=True)
    (100 * data.RC_C2).plot(legend=True)
    (100 * data.RC_C4).plot(legend=True)
    (100 * data.RC_C5).plot(legend=True)
    (100 * data.RC_C6).plot(legend=True)
    (100 * data.RC_C7).plot(legend=True)
    (100 * data.RC_C8).plot(legend=True)
    (100 * data.RC_C9).plot(legend=True)
    (100 * data.RC_C10).plot(legend=True)
    (100 * data.RC_C11).plot(legend=True)

    pl.legend(labels=rc_mapping)
    background_flight_modes(data)

def plot_acceleration_raw(data):

    pl.title('Raw Acceleration')
    pl.ylabel('m/s^2')

    data.IMU_AccX.plot(legend=True)
    data.IMU_AccY.plot(legend=True)
    data.IMU_AccZ.plot(legend=True)
    background_flight_modes(data)

def plot_angular_speed_raw(data):

    pl.title('Raw Angular Speed')
    pl.ylabel('deg/s')

    pl.rad2deg(data.IMU_GyroX).plot(legend=True)
    pl.rad2deg(data.IMU_GyroY).plot(legend=True)
    pl.rad2deg(data.IMU_GyroZ).plot(legend=True)
    background_flight_modes(data)

def plot_magnetic_raw(data):

    pl.title('Raw Magnetic Field Strengh')

    data.IMU_MagX.plot(legend=True)
    data.IMU_MagY.plot(legend=True)
    data.IMU_MagZ.plot(legend=True)
    background_flight_modes(data)

def plot_gps_stats(data):

    pl.title('GPS Statistics')

    data.GPS_EPH.plot(legend=True)
    data.GPS_EPV.plot(legend=True)
    data.GPS_nSat.plot(legend=True)
    background_flight_modes(data)

def plot_distance_sensor(data):

    pl.title('Distance Sensor')

    data.DIST_Distance.plot(legend=True)
    data.DIST_Covariance.plot(legend=True)
    background_flight_modes(data)

def plot_sonar_raw(data):

    pl.title('Raw Sonar Distance')

    data.FLOW_DtSonar.plot(legend=True)
    data.FLOW_DtSonar.plot(legend=True)
    background_flight_modes(data)

def plot_optical_flow_raw(data):

    pl.title('Raw Optical Flow Position')

    data.FLOW_RawX.plot(legend=True)
    data.FLOW_RawY.plot(legend=True)
    background_flight_modes(data)

def plot_optical_flow_quality(data):

    pl.title('Optical Flow Quality')

    data.FLOW_Qlty.plot(legend=True)
    background_flight_modes(data)

def _plot_outputs(data, channel):
    columns = ['OUT{0}_Out{1}'.format(channel, i) for i in range(0,8)]

    for c in columns:
        if (data[c].max() > 0):
            data[c].plot(legend=True)

def plot_px4io_outputs(data):
    """
    Plots outputs on PX4IO
    """

    pl.title('PX4IO Outputs')
    _plot_outputs(data, 0)
    background_flight_modes(data)

def plot_px4fmu_outputs(data):
    """
    Plots outputs on PX4FMU/AUX
    """
    pl.title('AUX Outputs')
    _plot_outputs(data, 1)
    background_flight_modes(data)

def statistics(df, keys=None, plot=False):
    data = {}
    for key in keys:
        try:
            df_meas = new_sample(df[key])
            dt = find_meas_period(df_meas)
            stddev = pl.sqrt(df_meas.var())
            mean = df_meas.mean()
            variance = stddev**2
            noise_power = variance*dt
        except Exception:
            df_meas = 0
            dt = 0
            stddev = 0
            var = 0
            mean = 0
            noise_power = 0
            variance = 0
        data[key+'_stddev'] = stddev
        data[key+'_variance'] = variance
        data[key+'_mean'] = mean
        data[key+'_dt'] = dt
        data[key+'_noise_power'] = noise_power
        if plot:
            pl.figure()
            pl.title(key + ' statistics')
            df[key].plot(alpha=0.5)
            pl.hlines(mean, df.index[0], df.index[-1], 'k')
            pl.hlines([mean + stddev, mean - stddev],
                    df.index[0], df.index[-1], 'r')
    return data

def find_lpe_gains(df, printing=False):
    keys = ['GPS_X', 'GPS_Y', 'GPS_Z', 'GPS_VelN', 'GPS_VelE', 'GPS_VelD',
            'DIST_Distance',
        'IMU1_AccX', 'IMU1_AccY', 'IMU1_AccZ', 'SENS_BaroAlt']
    stats = statistics(df, keys)

    params = {
        'LPE_LDR_Z': stats['DIST_Distance_stddev'],
        'LPE_BAR_Z': stats['SENS_BaroAlt_stddev'],
        'LPE_ACC_XY': pl.array([stats['IMU1_AccX_stddev'],
            stats['IMU1_AccX_noise_power']]).max(),
        'LPE_ACC_Z': stats['IMU1_AccZ_stddev'],
        'LPE_GPS_XY': pl.array([stats['GPS_X_stddev'],
            stats['GPS_Y_stddev']]).max(),
        'LPE_GPS_Z': stats['GPS_Z_stddev'],
        'LPE_GPS_VXY':  pl.array([stats['GPS_VelN_stddev'],
            stats['GPS_VelE_stddev']]).max(),
        'LPE_GPS_VZ':  stats['GPS_VelD_stddev']
    }

    if printing:
        for key in params.keys():
            print("{:s}\t=\t{:0.3g}".format(key, params[key]))
    return params

def new_sample(series):
    return series[pl.absolute(series.diff()) > 0]

def all_new_sample(df):
    df_new = pandas.DataFrame(df)
    for key in df.keys():
        df_new[key] = new_sample(df[key])
    return df_new

def find_meas_period(series):
    new = new_sample(series)
    return ((new.index[-1] - new.index[0])/
                len(new))

def plot_modes(data):

    data.STAT_MainState.plot()
    pl.ylim([0,13])
    pl.yticks(range(0,13), FLIGHT_MODES)
    background_flight_modes(data)

def background_flight_modes(data):
    """
    Overlays a background color for each flight mode. Can be called to style a graph.
    """
    modes = data.STAT_MainState.unique()
    colors_ = list(six.iteritems(colors.cnames))
    colors_.insert(0,'white')

    for m in modes:
        mode = data.STAT_MainState[data.STAT_MainState == m]
        t_min = mode.index[0]
        t_max = mode.index[mode.count() - 1]
        pl.axvspan(t_min, t_max, alpha=0.3, color=colors_[int(m)][0], label=FLIGHT_MODES[int(m)])


def process_lpe_health(data):
    names = ['baro', 'gps', 'lidar', 'flow', 'sonar', 'vision', 'mocap']
    try:
        faults = pl.array([[1 if (int(data.EST2_fHealth.values[i]) & 2**j) else 0
            for j in range(7)]
            for i in range(len(data.index))])
        for i in range(7):
            data['fault_' + names[i]] =  pandas.Series(
                data=faults[:,i], index=data.index, name='fault ' + names[i])
    except Exception as e:
        print(e)
    try:
        timeouts = pl.array([[0 if (int(data.EST0_fTOut.values[i]) & 2**j) else 1
            for j in range(7)]
            for i in range(len(data.index))])
        for i in range(7):
            data['timeout_' + names[i]] =  pandas.Series(
                data=timeouts[:,i], index=data.index, name='timeout ' + names[i])
    except Exception as e:
        print(e)
    return data

def plot_faults(data):
    try:
        data.fault_sonar.plot(alpha=0.1)
        data.fault_baro.plot()
        data.fault_gps.plot()
        data.fault_flow.plot()
        data.fault_vision.plot()
        data.fault_mocap.plot()
        data.fault_lidar.plot()
    except AttributeError as e:
        print(e)

# vim: set et fenc= ff=unix sts=0 sw=4 ts=4 :
