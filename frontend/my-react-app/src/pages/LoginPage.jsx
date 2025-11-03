import React, { useState } from 'react';
// import styles from './LoginPage.module.css'; 

function LoginPage() {


  return (
     <div style={{ padding: '2rem', textAlign: 'center' }}>
      <h1>로그인 페이지</h1>
      <p>이 화면이 보인다면, 라우터 연결에 성공한 것입니다.</p>

      {/* 기능이 없는 순수 HTML(JSX) 폼 뼈대입니다.
        <form> 태그는 기본적으로 제출 시 새로고침되므로, 
        테스트용으로는 <div>로 감싸거나 <form>을 빼는 것이 편합니다.
      */}
      <div>
        <div style={{ margin: '10px' }}>
          <label htmlFor="email_test">아이디: </label>
          <input id="email_test" type="text" placeholder="아이디 입력" />
        </div>
        
        <div style={{ margin: '10px' }}>
          <label htmlFor="pw_test">비밀번호: </label>
          <input id="pw_test" type="password" placeholder="비밀번호 입력" />
        </div>
        
        {/*
          <button type="submit">으로 하면 페이지가 새로고침됩니다.
          type="button"으로 하면 아무 동작도 하지 않습니다.
        */}
        <button type="button">
          로그인 (기능 없음)
        </button>
      </div>
      
    </div>
  );
}

export default LoginPage;