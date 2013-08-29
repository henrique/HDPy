"""
Analysis tools, specific for the *Puppy* experiment.
"""

import pylab
import h5py
import numpy as np
import itertools

sensor_names = ['trg0','trg1','trg2','trg3','accelerometer_x','accelerometer_y','accelerometer_z','compass_x','compass_y','compass_z','gyro_x','gyro_y','gyro_z','hip0','hip1','hip2','hip3','knee0','knee1','knee2','knee3','puppyGPS_x','puppyGPS_y','puppyGPS_z','touch0','touch0','touch1','touch2','touch3']

def puppy_plot_trajectory(analysis, axis, episode, step_width=1, offset=0, legend=True, **kwargs):
    """Plot the trajectory of an episode
    """
    gps_x = analysis[episode]['puppyGPS_x'][offset+step_width-1::step_width]
    gps_y = analysis[episode]['puppyGPS_y'][offset+step_width-1::step_width]
    if step_width > 1:
        gps_x = np.concatenate(([analysis[episode]['puppyGPS_x'][offset]], gps_x))
        gps_y = np.concatenate(([analysis[episode]['puppyGPS_y'][offset]], gps_y))

    col = kwargs.pop('color', 'k')
    label = kwargs.pop('label', 'Trajectory')
    axis.plot(gps_x, gps_y, color=col, **kwargs)
    axis.axis('equal')
    if legend:
        axis.plot(gps_x[0], gps_y[0], 'ks', label='Start')
        axis.plot(gps_x[-1], gps_y[-1], 'kv', label='End')
    
    return axis

def puppy_plot_all_trajectories(analysis, axis, step_width=1, **kwargs):
    """Plot all trajectories in ``analysis`` into ``axis``.
    """
    gps_x = analysis.get_data('puppyGPS_x')
    gps_y = analysis.get_data('puppyGPS_y')
    
    N = len(gps_x)-1
    kwargs.pop('color', None) # remove color argument
    for idx, (x, y) in enumerate(zip(gps_x, gps_y)):
        col = 0.75 - (0.75 * (idx - 1))/N
        
        x_plot = np.concatenate(([x[0]], x[step_width-1::step_width]))
        y_plot = np.concatenate(([y[0]], y[step_width-1::step_width]))
        
        axis.plot(x_plot, y_plot, color=str(col), **kwargs)
    
    return axis

def puppy_plot_linetarget(axis, origin=(2.0, 0.0), direction=(1.0, 1.0), range_=(-5.0, 5.0)):
    """Plot a line given by ``origin`` and ``direction``. The ``range_``
    may be supplid, which corresponds to the length of the line (from
    the origin).
    """
    origin = np.array(origin)
    dir_ = np.array(direction)
    dir_ /= np.linalg.norm(dir_)
    line = [origin + t * dir_ for t in range_]
    line_x, line_y = zip(*line)
    axis.plot(line_x, line_y, 'k', label='Target')
    return axis

def puppy_plot_locationtarget(axis, target=(4.0, 4.0), distance=0.5, **kwargs):
    """Plot the ``target`` location with a sphere of radius ``distance``
    into ``axis`` to mark the target location. ``kwargs`` will be passed
    to all :py:mod:`pylab` calls."""
    linewidth = kwargs.pop('linewidth', 2)
    color = kwargs.pop('facecolor', 'k')
    fill = kwargs.pop('fill', False)
    lbl = kwargs.pop('label', '')
    axis.plot([target[0]], [target[1]], 'kD', **kwargs)
    if distance > 0.0:
        trg_field = pylab.Circle(target, distance, fill=fill, facecolor=color, linewidth=linewidth, label=lbl, **kwargs)
        axis.add_artist(trg_field)

    return axis

def puppy_plot_landmarks(axis, landmarks, **kwargs):
    """Plot markers at ``landmark`` locations in ``axis``."""
    color = kwargs.pop('color', 'k')
    lbl = kwargs.pop('label', '')
    marker = kwargs.pop('marker','^')
    for x,y in landmarks:
        axis.plot([x],[y], marker=marker, color=color)
    return axis

def puppy_offline_playback(pth_data, critic, samples_per_action, ms_per_step, episode_start=None, episode_end=None):
    """Simulate an experiment run for the critic by using offline data.
    The data has to be collected in webots, using the respective
    robot and supervisor. Note that the behaviour of the simulation
    should match what's expected by the critic. The critic is fed the
    sensor data, in order. Of course, it can't react to it since
    the next action is predefined.
    
    Additional to the sensor fields, the 'tumbling' dataset is expected
    which indicates, if and when the robot has tumbled. It is used such
    that the respective signals can be sent to the critic.
    
    The critic won't store any sensory data again.
    
    ``pth_data``
        Path to the datafile with the sensory information (HDF5).
    
    ``critic``
        PuppyHDP instance.
    
    ``samples_per_action``
        Number of samples per control step. Must correspond to the data.
    
    ``ms_per_step``
        Sensor sampling period.
    
    ``episode_start``
        Defines a lower limit on the episode number. Passed as int,
        is with respect to the episode index, not its identifier.
    
    ``episode_stop``
        Defines an upper limit on the episode number. Passed as int,
        is with respect to the episode index, not its identifier.
    
    """
    # Open data file, get valid experiments
    f = h5py.File(pth_data,'r')
    storages = map(str, sorted(map(int, f.keys())))
    storages = filter(lambda s: len(f[s]) > 0, storages)
    
    if episode_end is not None:
        storages = storages[:episode_end]
    
    if episode_start is not None:
        storages = storages[episode_start:]
    
    assert len(storages) > 0
    
    # Prepare critic; redirect hooks to avoid storing epoch data twice
    # and feed the actions
    next_action = None
    critic._pre_increment_hook_orig = critic._pre_increment_hook
    critic._next_action_hook_orig = critic._next_action_hook
    
    def pre_increment_hook(epoch, **kwargs):
        critic._pre_increment_hook_orig(dict(), **kwargs)
    def next_action_hook(a_next):
        #print "(next)", a_next.T, next_action.T
        return next_action
    
    critic._next_action_hook = next_action_hook
    critic._pre_increment_hook = pre_increment_hook
    
    # Main loop, feed data to the critic
    time_step_ms = ms_per_step * samples_per_action
    time_start_ms = 0
    for episode_idx, episode in enumerate(storages):
        
        data_grp = f[episode]
        N = data_grp['trg0'].shape[0]
        assert N % samples_per_action == 0
        
        # get tumbled infos
        if 'tumbled' in data_grp:
            time_tumbled = data_grp['tumbled'][0] * samples_per_action
        else:
            time_tumbled = -1
        
        # initial, empty call
        if 'init_step' in data_grp:
            print "Simulation was started/reverted"
            time_start_ms = 0
            critic(dict(), time_start_ms, time_start_ms + samples_per_action, ms_per_step)
            time_tumbled -= samples_per_action
        
        # initial action
        critic.a_curr = np.atleast_2d(data_grp['a_curr'][0]).T
        
        # loop through data, incrementally feed the critic
        for num_iter in np.arange(0, N, samples_per_action):
            # next action
            next_action = np.atleast_2d(data_grp['a_next'][num_iter/samples_per_action]).T
            
            # get data
            time_start_ms += time_step_ms
            time_end_ms = time_start_ms + time_step_ms
            chunk = dict([(k, data_grp[k][num_iter:(num_iter+samples_per_action)]) for k in sensor_names])
            
            # send tumbled message
            if num_iter == time_tumbled:
                critic.event_handler(None, dict(), time_tumbled, 'tumbled_grace_start')
            
            # update critic
            critic(chunk, time_start_ms, time_end_ms, time_step_ms)
        
        # send reset after episode has finished
        if episode_idx < len(storages) - 1:
            critic.event_handler(None, dict(), ms_per_step * N, 'reset')
    
    # cleanup
    critic._pre_increment_hook = critic._pre_increment_hook_orig
    critic._next_action_hook = critic._next_action_hook_orig
    del critic._pre_increment_hook_orig
    del critic._next_action_hook_orig

def puppy_plot_action(analysis, episode, critic, reservoir, inspect_epochs, actions_range_x, actions_range_y, step_width, obs_offset):
    """
    
    .. todo::
        offset in case of offline data?
    
    .. todo::
        implementation unfinished, untested, undocumented
    
    """
    grp = analysis[episode]
    for trg_epoch in inspect_epochs:
        reservoir.reset()
        reservoir.states = np.atleast_2d(grp['x_curr'][trg_epoch-1,:])

        # evaluate actions
        # Note: epoch is one step ahead (of a_curr, same time as a_next)!
        # Note: sensor values are shifted w.r.t a_curr by obs_offset
        s_curr = dict([(sensor,grp[sensor][obs_offset+step_width*(trg_epoch-1):obs_offset+trg_epoch*step_width]) for sensor in sensor_names])
        a_ret = np.zeros((len(actions_range_x), len(actions_range_y)))

        actions_iter = itertools.product(range(len(actions_range_x)), range(len(actions_range_y)))
        for idx_x, idx_y in actions_iter:
            action_candidate = np.atleast_2d((actions_range_x[idx_x], actions_range_y[idx_y])).T
            j_curr = critic(s_curr, action_candidate, simulate=True)
            a_ret[idx_x, idx_y] = j_curr[0, 0]
            print actions_range_x[idx_x], actions_range_y[idx_y], j_curr[0, 0]

        # plot results
        fig = pylab.figure()
        pylab.gray()
        # In the image, the y-axis is the rows, the x-axis the columns of the matrix
        # Having index (0,0) in the left/bottom corner: origin='lower'
        pylab.plot((0, len(actions_range_x)-1), (0, len(actions_range_y)-1), 'b')
        pylab.imshow(a_ret, origin='lower')
        pylab.colorbar()
        pylab.xticks(range(len(actions_range_y)), actions_range_y)
        pylab.yticks(range(len(actions_range_x)), actions_range_x)
        pylab.title('Expected Return per action at epoch ' + str(trg_epoch))
        pylab.xlabel('Amplitude right legs') # cols are idx_y, right legs
        pylab.ylabel('Amplitude left legs') # rows are idx_x, left legs
    
    return fig
