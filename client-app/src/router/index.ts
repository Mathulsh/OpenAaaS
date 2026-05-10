import { createRouter, createWebHashHistory } from 'vue-router'
import HomeView from '@/views/HomeView.vue'
import ServiceDetailView from '@/views/ServiceDetailView.vue'
import SubmitTaskView from '@/views/SubmitTaskView.vue'
import TaskDetailView from '@/views/TaskDetailView.vue'
import TasksView from '@/views/TasksView.vue'
import SettingsView from '@/views/SettingsView.vue'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView,
      meta: { title: '服务市场' },
    },
    {
      path: '/service/:id',
      name: 'service-detail',
      component: ServiceDetailView,
      meta: { title: '服务详情' },
    },
    {
      path: '/submit/:serviceId',
      name: 'submit-task',
      component: SubmitTaskView,
      meta: { title: '提交任务' },
    },
    {
      path: '/task/:id',
      name: 'task-detail',
      component: TaskDetailView,
      meta: { title: '任务详情' },
    },
    {
      path: '/tasks',
      name: 'tasks',
      component: TasksView,
      meta: { title: '任务列表' },
    },
    {
      path: '/settings',
      name: 'settings',
      component: SettingsView,
      meta: { title: '设置' },
    },
  ],
})

export default router
