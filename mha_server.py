import json

from OpenMHA import MHAConnection
import server_common


def handle_conn_errors(func):

    def _func(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except TimeoutError as e:
            print(f"Connection timed out ({e}), attempting to reopen.")
            func.__self__._reopen()
        except BrokenPipeError as e:
            print(f"Connection broekn ({e}), attempting to reopen.")
            func.__self__._reopen()
        except Exception as e:
            print("Error handling message \"{}\": {}".format(
                (args if args else kwargs), e
            ))
    return _func


class LoopingWebSocket(server_common.MyWebSocketHandler):

    def __init__(self, *args, **kwargs):

        # grab our private keyword arguments
        self.mha_host = kwargs.pop('mha_host')
        self.mha_port = kwargs.pop('mha_port')
        self.interval = None
        self.pooling_id = kwargs.pop('pooling_id')
        pool_path = kwargs.pop('pool_path')

        # cache the location of the pooling plug-in
        self._mha_conn = MHAConnection(self.mha_host, self.mha_port,
                                       self.interval)
        self._plugin_path = self._mha_conn.find_id(self.pooling_id)[0]

        # If --pool-path was not passed, default to looking for a monitoring
        # plug-in in the same namespace as the acPooling_wave plug-in.
        if not pool_path:
            mon_path = self._plugin_path.replace(self.pooling_id, 'doasvm_mon')
            pool_path = mon_path + '.pool'
        self._pool_path = pool_path

        super(LoopingWebSocket, self).__init__(*args, **kwargs)

    def _send_data(self):

        try:
            p = self._mha_conn.get_val(self._pool_path)
            self.write_message(json.dumps({'data': p}))
        except ValueError as e:
            print(f"Error sending data: {e}")
        except TimeoutError as e:
            print(f"Connection timed out ({e}), attempting to reopen.")
            self._mha_conn._reopen()

    @handle_conn_errors
    def on_message(self, message):
        message = json.loads(message)

        if 'command' in message:
            if message['command'] == 'send_data':
                self._send_data()
            else:
                print('Unknown command "{}"'.format(message['command']))
        elif 'new_pooling_wndlen' in message:
            print(f'Pooling wndlen = {message["new_pooling_wndlen"]}')
            self._mha_conn.set_val(self._plugin_path + '.pooling_wndlen',
                                   message['new_pooling_wndlen'])
        elif 'new_pooling_alpha' in message:
            print(f'Pooling alpha = {message["new_pooling_alpha"]}')
            self._mha_conn.set_val(self._plugin_path + '.alpha',
                                   message['new_pooling_alpha'])
        elif 'new_pooling_type' in message:
            print(f'Pooling type = {message["new_pooling_type"]}')
            self._mha_conn.set_val(self._plugin_path + '.pooling_type',
                                   message['new_pooling_type'])
        elif 'beamformer' in message:
            print(f'Beamformer = {message["beamformer"]}')
            self._mha_conn.set_val(
                b'mha.doachain.post.select',
                ("Bf" if message['beamformer'] else "NoBf")
            )
        elif 'new_interval' in message:
            print(f'Interval = {message["new_interval"]}')
            self.interval = message['new_interval']
        else:
            print('Unknown message "{}"'.format(message))


if __name__ == '__main__':

    import argparse

    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    server_common.add_common_args(parser)
    parser.add_argument(
        '--mha-host',
        default='127.0.0.1',
        help='The host on which MHA is running.',
    )
    parser.add_argument(
        '--mha-port',
        default=33337,
        type=int,
        help='The port on which MHA is listening.',
    )
    parser.add_argument(
        '--classification-id',
        default='svm',
        type=str,
        help="""The ID of a doasvm_classification instance.  This is used to
        fetch the "angles" variable in order to pass additional parameters to
        the web app.
        """
    )
    parser.add_argument(
        '--pooling-id',
        default='pool',
        type=str,
        help="""The ID of the desired acPooling_wave instance.  This is the
        instance that will be controlled from the web app.
        """
    )
    parser.add_argument(
        '--pool-path',
        default='mha.doachain.doasvm_mon.pool',
        type=str,
        help="""The full path to the desired "pool" variable to visualise.  If
        unset, it is assumed that a doasvm_mon instance (named "doasvm_mon")
        exists in the same namespace as the pooling plug-in specified by
        --pooling-id, and that it has has a variable named "pool".
        """
    )
    args = parser.parse_args()

    # abort the connection after a 5 second timeout
    with MHAConnection(args.mha_host, args.mha_port, 5) as mha_conn:
        plugin_path = mha_conn.find_id(args.classification_id)
        if not plugin_path:
            exit('Error: Could not find plug-in with ID'
                 f'"{args.classification_id}"')
        angles = mha_conn.get_val(plugin_path[0] + '.angles')

    ws_args = (
        LoopingWebSocket, {'mha_host': args.mha_host,
                           'mha_port': args.mha_port,
                           'pooling_id': args.pooling_id,
                           'pool_path': args.pool_path}
    )

    server_common.main(args, ws_args, 'mha', min(angles), max(angles),
                       len(angles))
