import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import API from '../../../axiosInstance';

const initialState = {
    isAuthenticated: false,
    user: null,
    token: null,
    loading: false,
    error: null,
    isLoading: true, // For initial app loading
    // Get reset email from localStorage if exists
    resetEmail: localStorage.getItem('asaan_reset_email') || null,
    resetStep: null, // 'request', 'verify', 'reset' for tracking reset progress
    resetToken: localStorage.getItem('asaan_reset_token') || null,
  }; 

// Async Thunks
export const loginUser = createAsyncThunk(
  'auth/loginUser',
  async ({ email, password }, { rejectWithValue }) => {
    try {
      const res = await API.post('/auth/login', { email, password });
      return res.data;
    } catch (err) {
      return rejectWithValue(err.response?.data?.message || 'Login failed');
    }
  }
);

export const signupUser = createAsyncThunk(
  'auth/signupUser',
  async ({ name, email, password }, { rejectWithValue }) => {
    try {
      const res = await API.post('/auth/signup', { name, email, password });
      return res.data;
    } catch (err) {
      return rejectWithValue(err.response?.data?.message || 'Signup failed');
    }
  }
);

export const forgotPassword = createAsyncThunk(
  'auth/forgotPassword',
  async ({ email }, { rejectWithValue }) => {
    try {
      const response = await API.post('/auth/forgot-password', { email });
      return { email, ...response.data };
    } catch (error) {
      return rejectWithValue(error.response?.data?.message || 'Failed to send OTP');
    }
  }
);

export const verifyOTP = createAsyncThunk(
  'auth/verifyOTP',
  async ({ email, otp }, { rejectWithValue }) => {
    try {
      const response = await API.post('/auth/verify-otp', { email, otp });
      return response.data;
    } catch (error) {
      return rejectWithValue(error.response?.data?.message || 'Invalid OTP');
    }
  }
);

export const resetPassword = createAsyncThunk(
  'auth/resetPassword',
  async ({ email, newPassword, resetToken }, { rejectWithValue }) => { // Added resetToken
    try {
      const response = await API.post('/auth/reset-password', { 
        email, 
        newPassword,
        resetToken // Include the token from verifyOTP step
      });
      return response.data;
    } catch (error) {
      console.error('Reset Password Error:', error.response?.data);
      return rejectWithValue(error.response?.data?.message || 'Password reset failed');
    }
  }
);

const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    // action to load from localStorage
    loadFromStorage(state) {
        try {
          const savedAuth = localStorage.getItem('asaan_auth');
          const savedUser = localStorage.getItem('asaan_user');
          const savedToken = localStorage.getItem('asaan_token');
          
          if (savedAuth === 'true' && savedUser) {
            state.isAuthenticated = true;
            state.user = JSON.parse(savedUser);
            state.token = savedToken;
          }
        } catch (error) {
          console.error('Failed to load auth from storage:', error);
        }
        state.isLoading = false;
    },

    logout(state) {
      state.isAuthenticated = false;
      state.user = null;
      state.token = null;
      state.error = null;
      state.resetEmail = null;
      state.resetStep = null;
      state.isLoading = false;
      state.resetToken = null;

      localStorage.removeItem('asaan_auth');
      localStorage.removeItem('asaan_user');
      localStorage.removeItem('asaan_token');
      localStorage.removeItem('asaan_reset_email');
    },

    clearError(state) {
        state.error = null;
    },

    setResetEmail(state, action) {
        state.resetEmail = action.payload;
    },

    // Reset password flow management
    setResetStep(state, action) {
      state.resetStep = action.payload;
    },

    clearResetState(state) {
        state.resetEmail = null;
        state.resetStep = null;
        state.error = null;
        localStorage.removeItem('asaan_reset_email');
    },
  },
  extraReducers: (builder) => {
    // Login
    builder.addCase(loginUser.pending, (state) => {
      state.loading = true;
      state.error = null;
    });
    builder.addCase(loginUser.fulfilled, (state, action) => {
      const { user, token } = action.payload;
      state.isAuthenticated = true;
      state.user = {
        ...user,
        avatar: `https://api.dicebear.com/7.x/initials/svg?seed=${user.email}`
      };
      state.loading = false;
      state.resetEmail = null;
      state.resetStep = null;

      localStorage.setItem('asaan_auth', 'true');
      localStorage.setItem('asaan_user', JSON.stringify(state.user));
      localStorage.setItem('asaan_token', token);
    });
    builder.addCase(loginUser.rejected, (state, action) => {
      state.loading = false;
      state.error = action.payload;
    });

    // Signup
    builder.addCase(signupUser.pending, (state) => {
      state.loading = true;
      state.error = null;
    });
    builder.addCase(signupUser.fulfilled, (state, action) => {
      const { user, token } = action.payload;
      state.isAuthenticated = true;
      state.user = {
        ...user,
        avatar: `https://api.dicebear.com/7.x/initials/svg?seed=${user.email}`
      };
      state.loading = false;

      localStorage.setItem('asaan_auth', 'true');
      localStorage.setItem('asaan_user', JSON.stringify(state.user));
      localStorage.setItem('asaan_token', token);
    });
    builder.addCase(signupUser.rejected, (state, action) => {
      state.loading = false;
      state.error = action.payload;
    });

    // Forgot Password - Request OTP
    builder.addCase(forgotPassword.pending, (state) => {
      state.loading = true;
      state.error = null;
    });
    builder.addCase(forgotPassword.fulfilled, (state, action) => {
      state.loading = false;
      state.resetEmail = action.payload.email;
      state.resetStep = 'verify';
      state.error = null;
      // Save to localStorage
      localStorage.setItem('asaan_reset_email', action.payload.email);
      console.log('authSlice: forgotPassword.fulfilled');
      console.log('Email saved:', action.payload.email);
      console.log('Reset step set to:', 'verify');
    });
    builder.addCase(forgotPassword.rejected, (state, action) => {
      state.loading = false;
      state.error = action.payload;
      console.log('authSlice: forgotPassword.rejected', action.payload);
    });

    // Verify OTP
    builder.addCase(verifyOTP.pending, (state) => {
      state.loading = true;
      state.error = null;
    });
    builder.addCase(verifyOTP.fulfilled, (state, action) => {
      state.loading = false;
      state.resetStep = 'reset';
      state.error = null;
      state.resetToken = action.payload.resetToken;
      console.log('authSlice: verifyOTP.fulfilled - Step set to "reset"');
    });
    builder.addCase(verifyOTP.rejected, (state, action) => {
      state.loading = false;
      state.error = action.payload;
      console.log('authSlice: verifyOTP.rejected', action.payload);
    });

    // Reset Password
    builder.addCase(resetPassword.pending, (state) => {
      state.loading = true;
      state.error = null;
    });
    builder.addCase(resetPassword.fulfilled, (state, action) => {
      state.loading = false;
      state.resetEmail = null;
      state.resetStep = null;
      state.resetToken = null;
      state.error = null;
      // Clear from localStorage
      localStorage.removeItem('asaan_reset_email');
      console.log('authSlice: resetPassword.fulfilled - Reset state cleared');
    });
    builder.addCase(resetPassword.rejected, (state, action) => {
      state.loading = false;
      state.error = action.payload;
    });
  }
});

export const { 
    logout, 
    loadFromStorage, 
    clearError,
    setResetEmail,
    setResetStep,
    clearResetState
} = authSlice.actions;

export default authSlice.reducer;