import React, { useState } from 'react';
import styled, { css } from 'styled-components';
import apiClient from '../api/client';
import { useNavigate, Link } from 'react-router-dom';

// --- Styled Components ---

const Container = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  max-width: 380px;
  padding: 20px;
`;

const Header = styled.header`
  text-align: center;
  margin-bottom: 30px;
`;

const LogoText = styled.h1`
  font-size: 28px;
  color: #6200EE;
  margin: 0;
  font-weight: 800;
`;

const Subtitle = styled.p`
  font-size: 14px;
  color: #555;
  margin: 5px 0 0 0;
`;

const Title = styled.h2`
  font-size: 24px;
  font-weight: 700;
  color: #000;
  margin-bottom: 25px;
  align-self: flex-start;
`;

const Form = styled.form`
  display: flex;
  flex-direction: column;
  width: 100%;
`;

const Label = styled.label`
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-bottom: 8px;
`;

const Input = styled.input`
  width: 100%;
  padding: 16px 16px;
  font-size: 16px;
  border: 1px solid #E0E0E0;
  background-color: #F7F7F9;
  border-radius: 8px;
  margin-bottom: 16px;

  &::placeholder {
    color: #AAA;
  }

  &:focus {
    outline: none;
    border-color: #6200EE;
    box-shadow: 0 0 0 2px rgba(98, 0, 238, 0.2);
  }

  &:disabled {
    background-color: #EFEFEF;
    cursor: not-allowed;
  }
`;

const Button = styled.button`
  width: 100%;
  padding: 16px;
  font-size: 16px;
  font-weight: 700;
  border-radius: 8px;
  border: none;
  cursor: pointer;
  margin-top: 8px;
  transition: background-color 0.2s;

  ${(props) =>
    props.$primary &&
    css`
      background-color: #6200EE;
      color: white;
      
      &:hover {
        background-color: #5100C4;
      }
    `}
  
  &:disabled {
    background-color: #BDBDBD;
    cursor: not-allowed;
  }
`;

const InputGroup = styled.div`
  margin-bottom: 16px;
`;

const RadioButton = styled.input`
  margin-right: 8px;
`;

const RadioLabel = styled.label`
  font-size: 14px;
  color: #333;
  margin-right: 16px;
  cursor: pointer;
`;

const ErrorMessage = styled.p`
  font-size: 14px;
  color: #D32F2F;
  background-color: #FFEBEE;
  border: 1px solid #FFCDD2;
  border-radius: 8px;
  padding: 12px;
  width: 100%;
  text-align: center;
  margin: 0 0 16px 0;
`;

const Footer = styled.footer`
  margin-top: 30px;
  font-size: 12px;
  color: #AAA;
`;

const LoginLink = styled(Link)`
  font-size: 14px;
  color: #555;
  text-decoration: none;
  margin-top: 8px;
  
  &:hover {
    text-decoration: underline;
  }
`;

// --- React Component ---

function RegisterPage() {
  const [formData, setFormData] = useState({
    id: '',
    email: '',
    nickname: '',
    password: '',
    type: 'personal',
    organization_name: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  const navigate = useNavigate();

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const payload = { ...formData };
    if (payload.type === 'personal') {
      delete payload.organization_name;
    } else if (payload.type === 'organization' && !payload.organization_name) {
      setError('조직명을 입력해주세요.');
      setLoading(false);
      return;
    }

    const apiUrl = '/api/users/register'; // vite.config.js 

    try {
      const response = await apiClient.post(apiUrl, payload);
      
      console.log('Register Success:', response);
      alert('회원가입이 완료되었습니다. 로그인 페이지로 이동합니다.');
      navigate('/login');
      
    } catch (err) {
      if (err.response && err.response.data && err.response.data.detail) {
        setError(err.response.data.detail);
      } else {
        console.error('Register Error:', err);
        setError('회원가입 중 오류가 발생했습니다. 다시 시도해주세요.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container>
      <Header>
        <LogoText>Arcana</LogoText>
        <Subtitle>정보 파편화의 해결자 플랫폼</Subtitle>
      </Header>

      <Title>회원가입</Title>

      {error && <ErrorMessage>{error}</ErrorMessage>}

      <Form onSubmit={handleSubmit}>
        <Label htmlFor="id">아이디</Label>
        <Input name="id" id="id" type="text" value={formData.id} onChange={handleChange} disabled={loading} required />
        
        <Label htmlFor="email">이메일</Label>
        <Input name="email" id="email" type="email" value={formData.email} onChange={handleChange} disabled={loading} required />
        
        <Label htmlFor="nickname">닉네임</Label>
        <Input name="nickname" id="nickname" type="text" value={formData.nickname} onChange={handleChange} disabled={loading} required />
        
        <Label htmlFor="password">비밀번호</Label>
        <Input name="password" id="password" type="password" value={formData.password} onChange={handleChange} disabled={loading} required />

        <InputGroup>
          <Label>워크스페이스 유형</Label>
          <div>
            <RadioButton 
              type="radio" 
              id="type-personal" 
              name="type" 
              value="personal" 
              checked={formData.type === 'personal'} 
              onChange={handleChange}
              disabled={loading}
            />
            <RadioLabel htmlFor="type-personal">개인</RadioLabel>
            
            <RadioButton 
              type="radio" 
              id="type-organization" 
              name="type" 
              value="organization" 
              checked={formData.type === 'organization'} 
              onChange={handleChange}
              disabled={loading}
            />
            <RadioLabel htmlFor="type-organization">조직</RadioLabel>
          </div>
        </InputGroup>

        {formData.type === 'organization' && (
          <>
            <Label htmlFor="organization_name">조직명</Label>
            <Input 
              name="organization_name" 
              id="organization_name" 
              type="text" 
              value={formData.organization_name} 
              onChange={handleChange} 
              disabled={loading}
              placeholder="조직명을 입력하세요"
            />
          </>
        )}

        <Button type="submit" $primary disabled={loading}>
          {loading ? '가입 진행 중...' : '회원가입'}
        </Button>
      </Form>
      
      <LoginLink to="/login">
        이미 계정이 있으신가요? 로그인하러 가기
      </LoginLink>

      <Footer>Copyright ⓒ Arcana 모든 권리 보유</Footer>
    </Container>
  );
}

export default RegisterPage;

