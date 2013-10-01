"""
The analysis of ePuck experiments is conducted by looking at isolated
time steps of a testing or training situation. Three tools have been
implemented to support this procedure:
:py:func:`epuck_plot_all_trajectories` plots all training trajectories,
:py:func:`epuck_plot_value_over_action` creates a graph of the expected
return in a state as a function of the action.
:py:func:`epuck_plot_snapshot` plots the predicted return over an
example trajectory for several actions.

"""
import pylab
import numpy as np

def epuck_plot_all_trajectories(analysis, axis=None, key='loc'):
    """Plot trajectories of all episodes in ``analysis`` in the same
    plot ``axis``. The later an episode, the darker its trajectory is
    displayed. The trajectory data must be stored as ``key`` (default
    *loc*), a two-dimensional array. This function is intended to be
    used for analysis of **ePuck** experiments.
    """
    if axis is None:
        axis = pylab.figure().add_subplot(111)
    
    data = analysis.get_data(key)
    N = len(data)-1.0
    if N == 0.0:
        for idx, episode in enumerate(data):
            col = 0.0
            axis.plot(episode[:, 0], episode[:, 1], color=str(col), label=str(idx))
    else:
        for idx, episode in enumerate(data):
            #col = 0.75 - (0.75 * (idx - 1))/N
            col = 0.75 * (1.0 - float(idx) / N)
            axis.plot(episode[:, 0], episode[:, 1], color=str(col), label=str(idx))
    
    return axis

def _plot_line(axis, origin, angle, size_hi, size_lo=0.0, **kwargs):
    """Plot a straight line into ``axis``. The line is described through
    the ``origin`` and the ``angle``. It is drawn from ``size_lo`` to
    ``size_hi``, where both parameters are passed as fractions of said
    line. ``kwargs`` are passed to :py:meth:`pylab.plot`.
    """
    src = (origin[0] + np.cos(angle) * size_lo, origin[1] + np.sin(angle) * size_lo)
    trg = (origin[0] + np.cos(angle) * size_hi, origin[1] + np.sin(angle) * size_hi)
    axis.plot((src[0], trg[0]), (src[1], trg[1]), **kwargs)

def epuck_plot_value_over_action(critic, state, axis, a_range=None):
    """Given a trained ``critic``, plot the expected return as function
    of the action, given a ``state`` into ``axis``. Assuming 1-d action
    (otherwise, it becomes messy to plot). The default sampled actions
    range ``a_range`` is :math:`[0, 2\pi]` with step size 0.01.
    """
    if a_range is None:
        a_range = np.arange(0.0, 2*np.pi, 0.01)
    exp_return = np.vstack([critic(state, action%(2*np.pi), simulate=True) for action in a_range])
    axis.plot(a_range, exp_return, label='J(a|s)')
    axis.set_xlabel('action')
    axis.set_ylabel('Expected return')
    return axis

def epuck_plot_snapshot(axis, robot, critic, trajectory, sample_actions, init_steps=1, traj_chosen=None, inspected_steps=None):
    """Plot a snapshot of an *ePuck* experiment. The plot shows an
    example trajectory of the ``robot``, together with the expected
    return - i.e. evaluation of the ``critic`` at each state for some
    ``sample_actions``. Obviously, the ``critic`` needs to be
    pre-trained for this to make sense.
    
    ``axis``
        A :py:class:`pylab.Axis` to draw into.
    
    ``robot``
        The ePuck robot.
        
    ``critic``
        The pre-trained critic. It's supposed to be generated by
        :py:meth:`critic` (or implement the :py:meth:`critic_fu`
        interface).
    
    ``trajectory``
        Example trajectory the robot is moved along. 
    
    ``sample_actions``
        List of actions to be sampled and displayed at each step.
    
    ``init_steps``
        Number of steps the robot is initialized. During these steps,
        the robot is moved with action=0 but the ``critic`` not updated.
    
    ``traj_chosen``
        Represents the sequence of actions which was chosen by the
        algorithm at each step of the trajectory. If it is
        :py:keyword:`None`, it will be ignored. If not, it must be a
        list at least as long as ``trajectory``. 
    
    ``inspected_steps``
        List of step numbers, for which the expected return is plotted
        over the action, given the state at the respective step.
    
    """
    if traj_chosen is not None:
        assert len(traj_chosen) >= len(trajectory)
    else:
        traj_chosen = [None] * len(trajectory)
    
    if inspected_steps is None:
        inspected_steps = []
    
    robot_radius = 0.1
    robot_color = (0.0, 0.0, 0.0, 0.0) # white
    ray_len = robot_radius + 0.05
    
    for i in range(init_steps): # initialize
        robot.take_action(robot.pose)
    
    rays = []
    for num_step, (action_ex, action_chosen) in enumerate(zip(trajectory, traj_chosen)):
        
        # execute action, get the robot into the next state
        collided = robot.take_action(action_ex)
        s_curr = robot.read_sensors()
        
        # plot the robot
        loc_robot = s_curr['loc'][0]
        pose = s_curr['pose'][0, 0]
        if num_step % 2 == 0:
            rob = pylab.Circle(loc_robot, robot_radius, fill=True, facecolor=robot_color)
            axis.add_artist(rob)
            # plot the robot orientation
            _plot_line(axis, loc_robot, pose, robot_radius, color='k')
        
        #if action_chosen is not None:
        #    _plot_line(axis, loc_robot, pose+action_chosen, robot_radius+0.1, robot_radius, color='k', linewidth='2')
        
        if num_step % 2 == 0:
            # evaluate the critic on the actions
            p_returns = []
            #print ""
            for action_eval in sample_actions:
                predicted_return = critic(s_curr, action_eval, simulate=True)
                predicted_return = predicted_return[0, 0]
                p_returns.append((action_eval, predicted_return))
                #print action_eval, predicted_return
                
            # normalize returns
            r_offset = min([return_ for (action, return_) in p_returns])
            r_scale = max([return_ for (action, return_) in p_returns]) - r_offset
            
            for action_eval, predicted_return in p_returns:
                length = ray_len + 0.1 * (predicted_return - r_offset) / r_scale
                #rays.append((loc_robot, (pose+action_eval) % (2*np.pi), length, predicted_return)) # relative heading
                rays.append((loc_robot, (action_eval) % (2*np.pi), length, predicted_return)) # absolute heading

        if num_step in inspected_steps:
            fig_inspected = pylab.figure()
            epuck_plot_value_over_action(critic, s_curr, fig_inspected.add_subplot(111), a_range=np.arange(-2.0*np.pi, 2.0*np.pi, 0.01))
            fig_inspected.suptitle('Expected return in after %i steps (%s)' % (num_step, str(loc_robot)))
        
        # advance critic
        critic(s_curr, action_ex, simulate=False)
        
        if collided:
            break
    
    # normalize returns
    r_offset = min([predicted_return for (loc, ori, length, predicted_return) in rays])
    r_scale = max([predicted_return for (loc, ori, length, predicted_return) in rays]) - r_offset
    
    # plot rays
    for (loc, ori, length, predicted_return) in rays:
        nrm_return = (predicted_return - r_offset) / r_scale
        col = pylab.cm.hot(0.7 * nrm_return) # for the report
        #col = pylab.cm.spectral(nrm_return*0.25) # for the presentation
        
        # plot ray
        _plot_line(axis, loc, ori, size_hi=length+0.03, size_lo=robot_radius+0.03, color=col, linewidth=4)
    
    return axis


