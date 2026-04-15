const WECHAT_APPID = process.env.WECHAT_APPID?.trim() || '';
const WECHAT_APPSECRET = process.env.WECHAT_APPSECRET?.trim() || '';

interface Code2SessionResponse {
  openid?: string;
  unionid?: string;
  errcode?: number;
  errmsg?: string;
}

function assertWeChatReady() {
  if (!WECHAT_APPID || !WECHAT_APPSECRET) {
    throw new Error('微信小程序配置缺失，请补充 WECHAT_APPID / WECHAT_APPSECRET');
  }
}

async function requestJson<T>(url: string) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`微信接口请求失败：HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function exchangeCodeForOpenId(code: string) {
  assertWeChatReady();
  const cleanCode = String(code || '').trim();
  if (!cleanCode) {
    throw new Error('缺少微信登录 code');
  }

  const url = `https://api.weixin.qq.com/sns/jscode2session?appid=${encodeURIComponent(WECHAT_APPID)}&secret=${encodeURIComponent(WECHAT_APPSECRET)}&js_code=${encodeURIComponent(cleanCode)}&grant_type=authorization_code`;
  const data = await requestJson<Code2SessionResponse>(url);
  if (!data.openid) {
    throw new Error(`微信登录失败：${data.errmsg || data.errcode || '未知错误'}`);
  }

  return {
    openId: data.openid,
    unionId: data.unionid || '',
  };
}
