// src/context/AppContext.tsx
import React, { createContext, useContext, useReducer, ReactNode } from 'react';
import { mockIssues } from '../data/mockData';

interface User {
  id: string;
  name: string;
  phone: string;
  avatar?: string;
  address?: string;
  ward?: string;
}

interface Issue {
  id: string;
  title: string;
  description: string;
  category: 'roads' | 'sanitation' | 'water' | 'lighting';
  status: 'submitted' | 'in-progress' | 'resolved';
  date: string;
  image?: string;
  audio?: string;
  landmark?: string;
  upvotes: number;
  userId: string;
  location: { lat: number; lng: number };
}

interface CommunityPost {
  id: string;
  title: string;
  body?: string;
  image?: string;
  date?: string;
  userId: string;
  category?: 'roads' | 'sanitation' | 'water' | 'lighting';
  likes: string[]; // user ids who liked
}

interface AppState {
  user: User | null;
  issues: Issue[];
  notifications: any[];
  darkMode: boolean;
  language: 'en' | 'hi';
  communityPosts: CommunityPost[];
}

type AppAction = 
  | { type: 'SET_USER'; payload: User }
  | { type: 'ADD_ISSUE'; payload: Issue }
  | { type: 'UPDATE_ISSUE'; payload: { id: string; updates: Partial<Issue> } }
  | { type: 'DELETE_ISSUE'; payload: string }
  | { type: 'UPVOTE_ISSUE'; payload: string }
  | { type: 'ADD_NOTIFICATION'; payload: any }
  | { type: 'TOGGLE_DARK_MODE' }
  | { type: 'SET_LANGUAGE'; payload: 'en' | 'hi' }
  | { type: 'ADD_POST'; payload: CommunityPost }
  | { type: 'TOGGLE_LIKE'; payload: { postId: string } };

const initialState: AppState = {
  user: { id: 'u1', name: 'John Doe', phone: '1234567890' },
  issues: mockIssues,
  notifications: [],
  darkMode: false,
  language: 'en',
  communityPosts: [
    {
      id: 'p1',
      title: 'Blocked drain on Elm Street',
      body: 'Water has been pooling for weeks after heavy rains.',
      date: '2025-09-18',
      userId: 'u1',
      category: 'water',
      likes: []
    },
    {
      id: 'p2',
      title: 'Street light not working',
      body: 'Dark stretch near City Park entrance, unsafe at night.',
      date: '2025-09-19',
      userId: 'u2',
      category: 'lighting',
      likes: []
    },

     {
    id: 'p3',
    title: 'Blocked drain on Elm Street',
    body: 'Water has been pooling for weeks after heavy rains.',
    date: '2025-09-18',
    userId: 'u3',
    category: 'water',
    likes: []
  },
  {
    id: 'p4',
    title: 'Street light not working',
    body: 'Dark stretch near City Park entrance, unsafe at night.',
    date: '2025-09-19',
    userId: 'u4',
    category: 'lighting',
    likes: []
  },
  {
    id: 'p5',
    title: 'Garbage dumping near river',
    body: 'People are dumping trash daily, creating bad odor.',
    date: '2025-09-20',
    userId: 'u5',
    category: 'sanitation',
    likes: []
  },
  {
    id: 'p6',
    title: 'Pothole on Maple Avenue',
    body: 'Huge pothole causing traffic jams.',
    date: '2025-09-20',
    userId: 'u6',
    category: 'roads',
    likes: []
  },
  {
    id: 'p7',
    title: 'Water leak in main pipeline',
    body: 'Leakage has reduced water supply for nearby houses.',
    date: '2025-09-21',
    userId: 'u7',
    category: 'water',
    likes: []
  }
  ]
};

function appReducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case 'SET_USER':
      return { ...state, user: action.payload };
    case 'ADD_ISSUE':
      return { ...state, issues: [action.payload, ...state.issues] };
    case 'UPDATE_ISSUE':
      return {
        ...state,
        issues: state.issues.map(issue =>
          issue.id === action.payload.id
            ? { ...issue, ...action.payload.updates }
            : issue
        )
      };
    case 'DELETE_ISSUE':
      return {
        ...state,
        issues: state.issues.filter(issue => issue.id !== action.payload)
      };
    case 'UPVOTE_ISSUE':
      return {
        ...state,
        issues: state.issues.map(issue =>
          issue.id === action.payload
            ? { ...issue, upvotes: issue.upvotes + 1 }
            : issue
        )
      };
    case 'ADD_NOTIFICATION':
      return { ...state, notifications: [action.payload, ...state.notifications] };
    case 'TOGGLE_DARK_MODE':
      return { ...state, darkMode: !state.darkMode };
    case 'SET_LANGUAGE':
      return { ...state, language: action.payload };
    case 'ADD_POST':
      return { ...state, communityPosts: [action.payload, ...state.communityPosts] };
    case 'TOGGLE_LIKE': {
      const userId = state.user?.id;
      if (!userId) return state;

      const { postId } = action.payload;
      const updatedPosts = state.communityPosts.map(post => {
        if (post.id !== postId) return post;
        const alreadyLiked = post.likes.includes(userId);
        return {
          ...post,
          likes: alreadyLiked
            ? post.likes.filter(id => id !== userId)
            : [...post.likes, userId]
        };
      });
      return { ...state, communityPosts: updatedPosts };
    }
    default:
      return state;
  }
}

const AppContext = createContext<{
  state: AppState;
  dispatch: React.Dispatch<AppAction>;
} | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(appReducer, initialState);

  return (
    <AppContext.Provider value={{ state, dispatch }}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) throw new Error('useApp must be used within AppProvider');
  return context;
}
