import axios from 'axios';
import { clearTokens, getAccessToken, getRefreshToken, storeTokens } from './authStorage';

const apiClient = axios.create();
const plainClient = axios.create();

let refreshPromise = null;

const logoutAndRedirect = () => {
  clearTokens();
  // 로그인 화면으로 이동
  window.location.href = '/login';
};

const shouldAttemptRefresh = (detail) => {
  if (!detail) return false;
  return /토큰(이 )?만료|액세스 토큰이 필요/.test(detail);
};

const isHardFailure = (detail) => {
  return detail === 'Bearer 토큰이 필요합니다.' ||
    detail === '토큰 서명이 유효하지 않습니다.' ||
    detail === '사용자를 찾을 수 없습니다.';
};

const refreshAccessToken = async () => {
  if (!refreshPromise) {
    const refreshToken = getRefreshToken();
    if (!refreshToken) {
      throw new Error('리프레시 토큰이 없습니다.');
    }

    refreshPromise = plainClient.post('/api/users/token/refresh', { refresh_token: refreshToken })
      .then((response) => {
        storeTokens(response.data);
        return response.data.access_token;
      })
      .catch((error) => {
        logoutAndRedirect();
        throw error;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }

  return refreshPromise;
};

apiClient.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token && !config.headers?.Authorization) {
    config.headers = {
      ...config.headers,
      Authorization: `Bearer ${token}`,
    };
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const { response, config } = error;
    if (!response || !config) {
      return Promise.reject(error);
    }

    if (response.status !== 401 || config.__isRetryRequest) {
      return Promise.reject(error);
    }

    const detail = response.data?.detail;

    if (config.url?.includes('/token/refresh') || isHardFailure(detail)) {
      logoutAndRedirect();
      return Promise.reject(error);
    }

    if (!shouldAttemptRefresh(detail)) {
      logoutAndRedirect();
      return Promise.reject(error);
    }

    try {
      const newAccessToken = await refreshAccessToken();
      const retryConfig = {
        ...config,
        headers: {
          ...config.headers,
          Authorization: `Bearer ${newAccessToken}`,
        },
        __isRetryRequest: true,
      };
      return apiClient.request(retryConfig);
    } catch (refreshError) {
      return Promise.reject(refreshError);
    }
  }
);

export default apiClient;
export { storeTokens, clearTokens, getAccessToken, getRefreshToken };
