import ctypes
import traceback
from .dictstreamstate import StreamStateType
from ..helpers.nativedecorator import nativedecorator
from ..native.Python.InteropHelpers.InteropUtils import InteropUtils
from ..native.Python.QuixStreamsStreaming.States.StreamScalarState import StreamScalarState as sssi
from ..state.statevalue import StateValue

from typing import Generic, Callable


@nativedecorator
class ScalarStreamState(Generic[StreamStateType]):
    """
    Represents a state container that stores a scalar value with the ability to flush changes to a specified storage.
    """

    def __init__(self, net_pointer: ctypes.c_void_p, state_type: StreamStateType, default_value_factory: Callable[[], StreamStateType]):
        """
        Initializes a new instance of ScalarStreamState.

        NOTE: Do not initialize this class manually, use StreamStateManager.get_scalar_state

        Args:
            net_pointer: The .net object representing a ScalarStreamState.
            state_type: The type of the state
            default_value_factory: A function that returns a default value of type T when the value has not been set yet
        """

        if net_pointer is None:
            raise Exception("ScalarStreamState is none")

        if state_type is None:
            raise Exception('state_type must be specified')

        self._interop = sssi(net_pointer)
        self._default_value_factory = default_value_factory
        self._type = state_type

        self._in_memory_value = None

        # Define events and their reference holders
        self._on_flushed = None
        self._on_flushed_ref = None  # Keeping reference to avoid garbage collection

        self._on_flushing = None
        self._on_flushing_ref = None  # Keeping reference to avoid garbage collection

        # Check if type is immutable, because it needs special handling. Content could change without ScalarStreamState being
        # notified
        self._immutable = self._type in (int, float, bool, complex, str, bytes, bytearray, range)
        self._on_flushing_internal = None
        if not self._immutable:
            def on_flushing_internal():
                self._underlying_value = self._in_memory_value

            self._on_flushing_internal = on_flushing_internal
            self.on_flushing = None  # this will subscribe to the event and invoke the internal

    def _finalizerfunc(self):
        self._on_flushed_dispose()
        self._on_flushing_dispose()

    @property
    def type(self) -> type:
        """
        Gets the type of the ScalarStreamState

        Returns:
            StreamStateType: type of the state
        """
        return self._type

    # Region on_flushed
    @property
    def on_flushed(self) -> Callable[[], None]:
        """
        Gets the handler for when flush operation is completed.

        Returns:
            Callable[[], None]: The event handler for after flush.
        """
        return self._on_flushed

    @on_flushed.setter
    def on_flushed(self, value: Callable[[], None]) -> None:
        """
        Sets the handler for when flush operation is completed.

        Args:
            value: The parameterless callback to invoke
        """

        self._on_flushed = value
        if self._on_flushed_ref is not None:
            self._interop.remove_OnFlushed(self._on_flushed_ref)
            self._on_flushed_ref = None

        if self.on_flushed is None:
            return

        if self._on_flushed_ref is None:
            self._on_flushed_ref = self._interop.add_OnFlushed(self._on_flushed_wrapper)

    def _on_flushed_wrapper(self, sender_hptr, args_hptr):
        try:
            self._on_flushed(self._stream_consumer)
        except:
            traceback.print_exc()
        finally:
            InteropUtils.free_hptr(sender_hptr)
            InteropUtils.free_hptr(args_hptr)

    def _on_flushed_dispose(self):
        if self._on_flushed_ref is not None:
            self._interop.remove_OnFlushed(self._on_flushed_ref)
            self._on_flushed_ref = None

    # End region on_flushed

    # Region on_flushing
    @property
    def on_flushing(self) -> Callable[[], None]:
        """
        Gets the handler for when flush operation begins.

        Returns:
            Callable[[], None]: The event handler for after flush.
        """
        return self._on_flushing

    @on_flushing.setter
    def on_flushing(self, value: Callable[[], None]) -> None:
        """
        Sets the handler for when flush operation begins.

        Args:
            value: The parameterless callback to invoke
        """

        self._on_flushing = value
        if self._on_flushing_ref is not None:
            self._interop.remove_OnFlushing(self._on_flushing_ref)
            self._on_flushing_ref = None

        if self.on_flushing is None and self._on_flushing_internal is None:
            return

        if self._on_flushing_ref is None:
            self._on_flushing_ref = self._interop.add_OnFlushing(self._on_flushing_wrapper)

    def _on_flushing_wrapper(self, sender_hptr, args_hptr):
        try:
            if self._on_flushing is not None:
                self._on_flushing()
            if self._on_flushing_internal is not None:
                self._on_flushing_internal()
        except:
            traceback.print_exc()
        finally:
            InteropUtils.free_hptr(sender_hptr)
            InteropUtils.free_hptr(args_hptr)

    def _on_flushing_dispose(self):
        if self._on_flushing_ref is not None:
            self._interop.remove_OnFlushing(self._on_flushing_ref)
            self._on_flushing_ref = None

    # End region on_flushing

    def flush(self):
        """
        Flushes the changes made to the in-memory state to the specified storage.
        """
        self._interop.Flush()

    def reset(self):
        """
        Reset the state to before in-memory modifications
        """
        self._interop.Reset()

    @property
    def _underlying_value(self) -> StreamStateType:
        net_value = (self._interop.get_Value())
        if net_value is None:
            return None
        python_value = StateValue(net_value).value
        return python_value

    @_underlying_value.setter
    def _underlying_value(self, python_value: StreamStateType):
        if python_value is None:
            return None
        net_value = StateValue(python_value).get_net_pointer()
        self._interop.set_Value(net_value)


    @property
    def value(self):
        """
        Gets the value of the state.

        Returns:
            StreamStateType: The value of the state.
        """

        if self._in_memory_value is not None:
            return self._in_memory_value
        else:
            if self._underlying_value is not None:
                _value = self._underlying_value
            else:
                if self._default_value_factory is None:
                    raise

                value = self._default_value_factory()
                return value

            self._in_memory_value = _value
            return _value

    @value.setter
    def value(self, val: StreamStateType):
        """
        Sets the value of the state.

        Args:
            val: The value of the state.
        """
        self._in_memory_value = val
        self._underlying_value = val
