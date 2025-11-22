const storages = [typeof window !== 'undefined' ? window.sessionStorage : null, typeof window !== 'undefined' ? window.localStorage : null].filter(Boolean);

const copyToPrimaryAndReturn = (key, value, fromStorage) => {
  const primary = storages[0];
  if (value && primary && fromStorage !== primary) {
    primary.setItem(key, value);
    if (fromStorage) {
      fromStorage.removeItem(key);
    }
  }
  return value;
};

const readToken = (key) => {
  for (const storage of storages) {
    const value = storage?.getItem(key);
    if (value) {
      return copyToPrimaryAndReturn(key, value, storage);
    }
  }
  return null;
};

export const getAccessToken = () => readToken('accessToken');
export const getRefreshToken = () => readToken('refreshToken');

export const storeTokens = ({ access_token, refresh_token }) => {
  const primary = storages[0];
  if (primary) {
    if (access_token) primary.setItem('accessToken', access_token);
    if (refresh_token) primary.setItem('refreshToken', refresh_token);
  }
  // 토큰을 더 안전한 세션 스토리지에 보관하기 위해 로컬 스토리지 값은 제거한다.
  storages.forEach((storage, index) => {
    if (index > 0) {
      storage?.removeItem('accessToken');
      storage?.removeItem('refreshToken');
    }
  });
};

export const clearTokens = () => {
  storages.forEach((storage) => {
    storage?.removeItem('accessToken');
    storage?.removeItem('refreshToken');
  });
};
